"""Main entry point for the independent Flask + Dash data platform."""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from dataclasses import dataclass
from typing import Callable

import pandas as pd
from flask import Flask, redirect, render_template_string, send_from_directory

from dashboards.banking_dashboard import create_banking_dashboard
from dashboards.insurance_dashboard import create_insurance_dashboard
from dashboards.solar_page import render_solar_observatory_page
from database.data_loader import load_banking_data, load_insurance_data, load_solar_data
from preprocessing.scripts.preprocessing_solar import preprocess_solar_data

LOGGER = logging.getLogger(__name__)
DataLoader = Callable[[], pd.DataFrame]
ASSETS_DIR = Path(__file__).resolve().parent / 'assets'
DASHBOARDS_DIR = Path(__file__).resolve().parent / 'dashboards'


@dataclass(slots=True)
class DatasetState:
    """Runtime state associated with one MongoDB-backed dataset."""

    name: str
    dataframe: pd.DataFrame
    error_message: str | None = None


class DatasetRegistry:
    """Keep MongoDB datasets warm and reload them after transient failures."""

    def __init__(self, loaders: dict[str, DataLoader], fallback_loaders: dict[str, DataLoader] | None = None) -> None:
        self._loaders = loaders
        self._fallback_loaders = fallback_loaders or {}
        self._states = {
            name: DatasetState(name=name, dataframe=pd.DataFrame())
            for name in loaders
        }
        self._lock = threading.Lock()

    def get(self, name: str, *, refresh_if_unavailable: bool = True) -> DatasetState:
        """Return one dataset state, retrying the load when it is unavailable."""

        with self._lock:
            state = self._states[name]
            should_refresh = refresh_if_unavailable and (state.error_message is not None or state.dataframe.empty)

        if should_refresh:
            return self.refresh(name, force=True)

        with self._lock:
            return self._states[name]

    def refresh(self, name: str, *, force: bool = False) -> DatasetState:
        """Reload one dataset while preserving the last good payload on failure."""

        loader = self._loaders[name]

        with self._lock:
            state = self._states[name]
            if not force and state.error_message is None and not state.dataframe.empty:
                return state

        try:
            dataframe = loader()
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Unable to refresh the %s dataset from MongoDB: %s", name, exc)
            fallback_loader = self._fallback_loaders.get(name)
            if fallback_loader is not None:
                try:
                    fallback_dataframe = fallback_loader()
                except Exception as fallback_exc:  # noqa: BLE001
                    LOGGER.warning("Unable to build the %s fallback dataset: %s", name, fallback_exc)
                else:
                    with self._lock:
                        state = self._states[name]
                        state.dataframe = fallback_dataframe
                        state.error_message = f"MongoDB indisponible. Repli local actif: {exc}"
                        return state

            with self._lock:
                state = self._states[name]
                state.error_message = str(exc)
                if state.dataframe.empty:
                    state.dataframe = pd.DataFrame()
                return state

        with self._lock:
            state = self._states[name]
            state.dataframe = dataframe
            state.error_message = None
            return state

    def refresh_all(self, *, force: bool = False) -> dict[str, DatasetState]:
        """Reload all datasets and return the current application snapshot."""

        for name in self._loaders:
            if force:
                self.refresh(name, force=True)
            else:
                self.get(name, refresh_if_unavailable=True)
        return self.snapshot()

    def snapshot(self, *, refresh_if_unavailable: bool = False) -> dict[str, DatasetState]:
        """Return the current state for every dataset."""

        if refresh_if_unavailable:
            for name in self._loaders:
                self.get(name, refresh_if_unavailable=True)

        with self._lock:
            return {name: self._states[name] for name in self._states}


HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Younes Hachami - Data Visualisation Multi-Sectorielle</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=IBM+Plex+Mono:wght@300;400;500&family=Fraunces:ital,opsz,wght@0,9..144,300;1,9..144,300&display=swap" rel="stylesheet"/>
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css" rel="stylesheet"/>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { scroll-behavior: smooth; }
:root {
  --bg: #07090f;
  --bg-card: #0c1118;
  --gold: #c9a84c;
  --gold2: #f0c455;
  --gold-glow: rgba(201,168,76,0.18);
  --cyan: #4ecdc4;
  --purple: #a29bfe;
  --amber: #f7b731;
  --text: #dde1ec;
  --text-dim: #6b7591;
  --border: rgba(201,168,76,0.14);
  --banking: #4ecdc4;
  --energy: #f7b731;
  --insurance: #a29bfe;
  --r: 14px;
}
body {
  background: var(--bg);
  color: var(--text);
  font-family: 'Syne', sans-serif;
  overflow-x: hidden;
  min-height: 100vh;
}
.bg-layer {
  position: fixed; inset: 0; z-index: 0; overflow: hidden; pointer-events: none;
}
.bg-orb {
  position: absolute; border-radius: 50%; filter: blur(120px); opacity: .13;
  animation: orbFloat 18s ease-in-out infinite alternate;
}
.bg-orb:nth-child(1) { width: 700px; height: 700px; background: var(--gold); top: -200px; left: -150px; animation-delay: 0s; }
.bg-orb:nth-child(2) { width: 500px; height: 500px; background: var(--cyan); bottom: 0; right: -100px; animation-delay: -6s; }
.bg-orb:nth-child(3) { width: 400px; height: 400px; background: var(--purple); top: 50%; left: 40%; animation-delay: -12s; }
@keyframes orbFloat { from { transform: translate(0,0) scale(1); } to { transform: translate(30px,40px) scale(1.08); } }
.bg-grid {
  position: fixed; inset: 0; z-index: 0; pointer-events: none;
  background-image:
    linear-gradient(rgba(201,168,76,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(201,168,76,0.04) 1px, transparent 1px);
  background-size: 60px 60px;
}
.page { position: relative; z-index: 1; }
.wrap { max-width: 1120px; margin: 0 auto; padding: 0 2rem; }
.topbar {
  position: fixed; top: 0; left: 0; right: 0; z-index: 100; height: 58px;
  background: rgba(7,9,15,0.88); backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
}
.topbar .wrap {
  height: 100%; display: flex; align-items: center; justify-content: space-between;
}
.topbar-brand {
  font-family: 'IBM Plex Mono', monospace; font-size: .7rem; letter-spacing: .16em; color: var(--gold);
  text-transform: uppercase;
}
.topbar-brand span { color: var(--text-dim); }
.topbar-nav { display: flex; gap: 1.8rem; align-items: center; }
.topbar-nav a {
  font-family: 'IBM Plex Mono', monospace; font-size: .68rem; letter-spacing: .1em; color: var(--text-dim);
  text-decoration: none; text-transform: uppercase; transition: color .2s;
}
.topbar-nav a:hover { color: var(--gold2); }
.github-btn {
  display: inline-flex; align-items: center; gap: .45rem; background: var(--gold-glow);
  border: 1px solid var(--border); border-radius: 6px; padding: .38rem .9rem;
  font-family: 'IBM Plex Mono', monospace; font-size: .68rem; letter-spacing: .1em; color: var(--gold);
  text-decoration: none; text-transform: uppercase;
  transition: background .2s, border-color .2s, color .2s;
}
.github-btn:hover { background: rgba(201,168,76,0.28); border-color: var(--gold); color: var(--gold2); }
.github-btn svg { width: 14px; height: 14px; fill: currentColor; }
.hero {
  min-height: 100vh; display: flex; align-items: center; padding-top: 80px; padding-bottom: 60px;
}
.hero-inner { display: grid; grid-template-columns: 1fr 420px; gap: 4rem; align-items: center; }
.hero-badge {
  display: inline-flex; align-items: center; gap: .6rem; background: var(--gold-glow);
  border: 1px solid var(--border); border-radius: 100px; padding: .35rem 1rem;
  font-family: 'IBM Plex Mono', monospace; font-size: .65rem; letter-spacing: .14em; color: var(--gold);
  text-transform: uppercase; margin-bottom: 1.8rem; opacity: 0; animation: fadeUp .5s .1s forwards;
}
.hero-badge::before {
  content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--gold);
  box-shadow: 0 0 8px var(--gold); animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse { 0%,100% { opacity: 1; transform: scale(1); } 50% { opacity: .5; transform: scale(.85); } }
.hero-title {
  font-size: clamp(2.6rem, 6vw, 5.2rem); font-weight: 800; line-height: 1; letter-spacing: -.03em;
  margin-bottom: 1.4rem; opacity: 0; animation: fadeUp .6s .22s forwards;
}
.hero-title em {
  font-style: normal; color: transparent; -webkit-text-stroke: 1.5px var(--gold); display: block;
}
.hero-subtitle {
  font-family: 'Fraunces', serif; font-size: 1.05rem; font-weight: 300; font-style: italic;
  color: var(--text-dim); line-height: 1.7; margin-bottom: 2rem; max-width: 520px;
  opacity: 0; animation: fadeUp .6s .34s forwards;
}
.hero-meta {
  display: flex; gap: 2rem; flex-wrap: wrap; margin-bottom: 2.4rem;
  opacity: 0; animation: fadeUp .6s .44s forwards;
}
.hero-meta-item { display: flex; flex-direction: column; gap: .2rem; }
.hero-meta-label {
  font-family: 'IBM Plex Mono', monospace; font-size: .6rem; letter-spacing: .14em; color: var(--text-dim);
  text-transform: uppercase;
}
.hero-meta-value { font-size: .88rem; font-weight: 600; color: var(--text); }
.hero-cta {
  display: flex; gap: 1rem; flex-wrap: wrap; opacity: 0; animation: fadeUp .6s .54s forwards;
}
.btn-primary, .btn-secondary {
  display: inline-flex; align-items: center; gap: .5rem; padding: .75rem 1.6rem; border-radius: 8px;
  text-decoration: none; transition: .2s ease; cursor: pointer;
}
.btn-primary {
  background: var(--gold); color: #07090f; font-size: .82rem; font-weight: 700; letter-spacing: .04em;
}
.btn-primary:hover { background: var(--gold2); transform: translateY(-2px); }
.btn-secondary {
  background: transparent; border: 1px solid var(--border); color: var(--text-dim);
  font-size: .82rem; font-weight: 600; letter-spacing: .04em;
}
.btn-secondary:hover { border-color: var(--gold); color: var(--gold); transform: translateY(-2px); }
.hero-visual { opacity: 0; animation: fadeLeft .8s .3s forwards; }
.stat-card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--r); padding: 1.6rem;
  position: relative; overflow: hidden;
}
.stat-card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: linear-gradient(90deg, var(--gold), transparent);
}
.stat-card-title {
  font-family: 'IBM Plex Mono', monospace; font-size: .65rem; letter-spacing: .14em; color: var(--gold);
  text-transform: uppercase; margin-bottom: 1.2rem;
}
.stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.2rem; }
.stat-item {
  background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; padding: .9rem;
}
.stat-num { font-size: 1.6rem; font-weight: 800; color: var(--gold2); line-height: 1; margin-bottom: .25rem; }
.stat-lbl {
  font-family: 'IBM Plex Mono', monospace; font-size: .58rem; letter-spacing: .1em; color: var(--text-dim); text-transform: uppercase;
}
.stat-divider { height: 1px; background: var(--border); margin: 1rem 0; }
.db-row { display: flex; align-items: center; gap: .7rem; padding: .5rem 0; }
.db-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.db-label { font-family: 'IBM Plex Mono', monospace; font-size: .7rem; color: var(--text); flex: 1; }
.db-val { font-family: 'IBM Plex Mono', monospace; font-size: .68rem; color: var(--text-dim); }
.section-label {
  font-family: 'IBM Plex Mono', monospace; font-size: .65rem; letter-spacing: .18em; color: var(--gold);
  text-transform: uppercase; margin-bottom: .7rem;
}
.section-title {
  font-size: clamp(1.8rem, 3.5vw, 2.6rem); font-weight: 800; letter-spacing: -.025em;
  line-height: 1.1; margin-bottom: .8rem;
}
.section-sub {
  font-family: 'Fraunces', serif; font-size: .95rem; font-weight: 300; font-style: italic;
  color: var(--text-dim); line-height: 1.7; max-width: 560px;
}
.dashboards { padding: 80px 0; }
.dashboards-header {
  margin-bottom: 3rem; display: flex; align-items: flex-end; justify-content: space-between; flex-wrap: wrap; gap: 1.5rem;
}
.dash-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; }
.dash-card {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--r); padding: 2rem;
  position: relative; overflow: hidden; display: flex; flex-direction: column;
  transition: border-color .3s, transform .3s, box-shadow .3s; text-decoration: none; color: inherit;
}
.dash-card:hover { transform: translateY(-6px); box-shadow: 0 24px 60px rgba(0,0,0,.5); }
.dash-card.banking:hover { border-color: var(--banking); box-shadow: 0 24px 60px rgba(78,205,196,0.1); }
.dash-card.energy:hover { border-color: var(--energy); box-shadow: 0 24px 60px rgba(247,183,49,0.1); }
.dash-card.insurance:hover { border-color: var(--insurance); box-shadow: 0 24px 60px rgba(162,155,254,0.1); }
.dash-card-stripe {
  position: absolute; top: 0; left: 0; right: 0; height: 3px; background: currentColor; transition: height .3s;
}
.banking .dash-card-stripe { color: var(--banking); }
.energy .dash-card-stripe { color: var(--energy); }
.insurance .dash-card-stripe { color: var(--insurance); }
.dash-card:hover .dash-card-stripe { height: 4px; }
.dash-card-bg {
  position: absolute; bottom: -30px; right: -30px; width: 140px; height: 140px; border-radius: 50%; opacity: .045; transition: .3s ease;
}
.banking .dash-card-bg { background: var(--banking); }
.energy .dash-card-bg { background: var(--energy); }
.insurance .dash-card-bg { background: var(--insurance); }
.dash-card:hover .dash-card-bg { opacity: .09; transform: scale(1.2); }
.dash-icon {
  width: 44px; height: 44px; border-radius: 10px; display: flex; align-items: center; justify-content: center;
  margin-bottom: 1.2rem; font-size: 1.3rem; position: relative; z-index: 1;
}
.banking .dash-icon { background: rgba(78,205,196,0.12); }
.energy .dash-icon { background: rgba(247,183,49,0.12); }
.insurance .dash-icon { background: rgba(162,155,254,0.12); }
.dash-sector {
  font-family: 'IBM Plex Mono', monospace; font-size: .6rem; letter-spacing: .16em; text-transform: uppercase;
  margin-bottom: .5rem; position: relative; z-index: 1;
}
.banking .dash-sector { color: var(--banking); }
.energy .dash-sector { color: var(--energy); }
.insurance .dash-sector { color: var(--insurance); }
.dash-card-title { font-size: 1.2rem; font-weight: 700; margin-bottom: .7rem; position: relative; z-index: 1; }
.dash-card-desc {
  font-family: 'Fraunces', serif; font-size: .87rem; font-weight: 300; color: var(--text-dim);
  line-height: 1.65; flex: 1; margin-bottom: 1.5rem; position: relative; z-index: 1;
}
.dash-tags { display: flex; flex-wrap: wrap; gap: .4rem; margin-bottom: 1.5rem; position: relative; z-index: 1; }
.dash-tag {
  font-family: 'IBM Plex Mono', monospace; font-size: .58rem; letter-spacing: .08em; padding: .28rem .65rem;
  border-radius: 100px; text-transform: uppercase; background: rgba(255,255,255,0.04);
  border: 1px solid rgba(255,255,255,0.08); color: var(--text-dim);
}
.dash-open-btn {
  display: inline-flex; align-items: center; gap: .5rem; font-size: .78rem; font-weight: 700;
  padding: .65rem 1.2rem; border-radius: 7px; text-decoration: none; transition: opacity .2s, transform .2s;
  position: relative; z-index: 1; align-self: flex-start;
}
.banking .dash-open-btn { background: var(--banking); color: #07090f; }
.energy .dash-open-btn { background: var(--energy); color: #07090f; }
.insurance .dash-open-btn { background: var(--insurance); color: #07090f; }
.dash-open-btn:hover { opacity: .88; transform: translateX(3px); }
.dashboards-arrow { width: 14px; height: 14px; }
.about { padding: 80px 0; border-top: 1px solid var(--border); }
.about-inner { display: grid; grid-template-columns: 1fr 1fr; gap: 4rem; align-items: start; }
.about-blocks { display: flex; flex-direction: column; gap: 1.2rem; }
.about-block {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: 10px; padding: 1.4rem 1.6rem;
  position: relative; transition: border-color .25s;
}
.about-block:hover { border-color: rgba(201,168,76,0.35); }
.about-block-title { font-size: .82rem; font-weight: 700; margin-bottom: .5rem; display: flex; align-items: center; gap: .5rem; }
.about-block-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.about-block p {
  font-family: 'Fraunces', serif; font-size: .85rem; font-weight: 300; color: var(--text-dim); line-height: 1.65;
}
.tech-panel {
  background: var(--bg-card); border: 1px solid var(--border); border-radius: var(--r); padding: 2rem; height: fit-content;
  position: sticky; top: 80px;
}
.tech-panel-title {
  font-family: 'IBM Plex Mono', monospace; font-size: .65rem; letter-spacing: .14em; color: var(--gold);
  text-transform: uppercase; margin-bottom: 1.4rem;
}
.tech-items { display: flex; flex-direction: column; gap: .65rem; }
.tech-item {
  display: flex; align-items: center; gap: 1rem; padding: .75rem 1rem; background: rgba(255,255,255,0.03);
  border: 1px solid rgba(255,255,255,0.06); border-radius: 8px; transition: border-color .2s;
}
.tech-item:hover { border-color: var(--border); }
.tech-icon { font-size: 1.2rem; width: 32px; text-align: center; }
.tech-info { flex: 1; }
.tech-name { font-size: .82rem; font-weight: 600; }
.tech-role { font-family: 'IBM Plex Mono', monospace; font-size: .6rem; color: var(--text-dim); letter-spacing: .06em; }
footer { border-top: 1px solid var(--border); padding: 2.5rem 0; }
footer .wrap {
  display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 1rem;
}
.footer-left {
  font-family: 'IBM Plex Mono', monospace; font-size: .65rem; letter-spacing: .1em; color: var(--text-dim); text-transform: uppercase;
}
.footer-left strong { color: var(--gold); }
.footer-right { display: flex; align-items: center; gap: 1.5rem; }
.footer-right a {
  font-family: 'IBM Plex Mono', monospace; font-size: .62rem; letter-spacing: .08em; color: var(--text-dim);
  text-decoration: none; text-transform: uppercase; transition: color .2s;
}
.footer-right a:hover { color: var(--gold); }
@keyframes fadeUp {
  from { opacity: 0; transform: translateY(22px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes fadeLeft {
  from { opacity: 0; transform: translateX(28px); }
  to { opacity: 1; transform: translateX(0); }
}
.reveal { opacity: 0; transform: translateY(24px); transition: opacity .65s ease, transform .65s ease; }
.reveal.visible { opacity: 1; transform: none; }
.reveal-delay-1 { transition-delay: .1s; }
.reveal-delay-2 { transition-delay: .2s; }
.reveal-delay-3 { transition-delay: .3s; }
@media (max-width: 900px) {
  .hero-inner { grid-template-columns: 1fr; }
  .hero-visual { display: none; }
  .dash-grid { grid-template-columns: 1fr 1fr; }
  .about-inner { grid-template-columns: 1fr; }
  .tech-panel { position: static; }
  .dashboards-header { flex-direction: column; align-items: flex-start; }
}
@media (max-width: 760px) {
  .topbar { height: auto; padding: .75rem 0; }
  .topbar .wrap { min-height: auto; flex-direction: column; align-items: flex-start; gap: .75rem; }
  .topbar-nav { width: 100%; flex-wrap: wrap; gap: .9rem; }
  .hero { padding-top: 136px; }
  .hero-meta { gap: 1rem; }
  .hero-cta { width: 100%; }
  .btn-primary, .btn-secondary { width: 100%; justify-content: center; }
}
@media (max-width: 600px) {
  .wrap { padding: 0 1.2rem; }
  .dash-grid { grid-template-columns: 1fr; }
  .stat-grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="bg-layer">
  <div class="bg-orb"></div>
  <div class="bg-orb"></div>
  <div class="bg-orb"></div>
</div>
<div class="bg-grid"></div>
<div class="page">
  <nav class="topbar">
    <div class="wrap">
      <div class="topbar-brand">YH<span> / </span>DataViz</div>
      <div class="topbar-nav">
        <a href="#dashboards">Dashboards</a>
        <a href="#about">&Agrave; propos</a>
        <a href="{{ github_url }}" target="_blank" rel="noreferrer" class="github-btn">
          <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 .3a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2 0-.4-.5-1.6.2-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0C17 6.1 18 6.4 18 6.4c.7 1.6.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.5.4.9 1.2.9 2.3v3.4c0 .3.2.7.8.6A12 12 0 0 0 12 .3"/></svg>
          GitHub
        </a>
      </div>
    </div>
  </nav>

  <section class="hero">
    <div class="wrap">
      <div class="hero-inner">
        <div class="hero-left">
          <div class="hero-badge">Projet de fin d&apos;&eacute;tudes &middot; {{ project_year }}</div>
          <h1 class="hero-title">
            Younes<br>Hachami
            <em>Data Visualisation</em>
          </h1>
          <p class="hero-subtitle">
            Conception et r&eacute;alisation de trois dashboards interactifs multi-sectoriels &mdash; bancaire, &eacute;nerg&eacute;tique et assurance &mdash; int&eacute;gr&eacute;s dans une application Flask &middot; Dash &middot; MongoDB.
          </p>
          <div class="hero-meta">
            {% for item in hero_meta %}
            <div class="hero-meta-item">
              <span class="hero-meta-label">{{ item.label }}</span>
              <span class="hero-meta-value">{{ item.value }}</span>
            </div>
            {% endfor %}
          </div>
          <div class="hero-cta">
            <a href="#dashboards" class="btn-primary">
              Voir les dashboards
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M7 17l9.2-9.2M17 17V7H7"/></svg>
            </a>
            <a href="{{ github_url }}" target="_blank" rel="noreferrer" class="btn-secondary">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 .3a12 12 0 0 0-3.8 23.4c.6.1.8-.3.8-.6v-2c-3.3.7-4-1.6-4-1.6-.6-1.4-1.4-1.8-1.4-1.8-1-.7.1-.7.1-.7 1.2.1 1.8 1.2 1.8 1.2 1 1.8 2.8 1.3 3.5 1 .1-.8.4-1.3.7-1.6-2.7-.3-5.5-1.3-5.5-5.9 0-1.3.5-2.4 1.2-3.2 0-.4-.5-1.6.2-3.2 0 0 1-.3 3.3 1.2a11.5 11.5 0 0 1 6 0C17 6.1 18 6.4 18 6.4c.7 1.6.2 2.9.1 3.2.8.8 1.2 1.9 1.2 3.2 0 4.6-2.8 5.6-5.5 5.9.5.4.9 1.2.9 2.3v3.4c0 .3.2.7.8.6A12 12 0 0 0 12 .3"/></svg>
              Repo GitHub
            </a>
          </div>
        </div>

        <div class="hero-visual">
          <div class="stat-card">
            <div class="stat-card-title">// &Eacute;tat des datasets</div>
            <div class="stat-grid">
              {% for stat in hero_stats %}
              <div class="stat-item">
                <div class="stat-num">{{ stat.value }}</div>
                <div class="stat-lbl">{{ stat.label }}</div>
              </div>
              {% endfor %}
            </div>
            <div class="stat-divider"></div>
            {% for row in dataset_rows %}
            <div class="db-row">
              <div class="db-dot" style="background:var(--{{ row.slug }})"></div>
              <span class="db-label">{{ row.label }}</span>
              <span class="db-val">{{ row.status }}</span>
            </div>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
  </section>

  <section class="dashboards" id="dashboards">
    <div class="wrap">
      <div class="dashboards-header reveal">
        <div>
          <div class="section-label">// Acc&egrave;s aux dashboards</div>
          <h2 class="section-title">Trois secteurs,<br>une plateforme</h2>
        </div>
        <p class="section-sub">
          Chaque dashboard est ind&eacute;pendant, mont&eacute; sur sa propre route avec sa logique, ses graphiques et son identit&eacute; visuelle.
        </p>
      </div>

      <div class="dash-grid">
        {% for card in cards %}
        <a href="{{ card.href }}" class="dash-card {{ card.slug }} reveal reveal-delay-{{ loop.index }}"{% if card.new_tab %} target="_blank" rel="noreferrer"{% endif %}>
          <div class="dash-card-stripe"></div>
          <div class="dash-card-bg"></div>
          <div class="dash-icon">{{ card.icon | safe }}</div>
          <div class="dash-sector">{{ card.sector }}</div>
          <div class="dash-card-title">{{ card.title }}</div>
          <p class="dash-card-desc">{{ card.description }}</p>
          <div class="dash-tags">
            {% for tag in card.tags %}
            <span class="dash-tag">{{ tag }}</span>
            {% endfor %}
          </div>
          <span class="dash-open-btn">
            Ouvrir le dashboard
            <svg class="dashboards-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M7 17l9.2-9.2M17 17V7H7"/></svg>
          </span>
        </a>
        {% endfor %}
      </div>
    </div>
  </section>

  <section class="about" id="about">
    <div class="wrap">
      <div class="about-inner">
        <div>
          <div class="section-label reveal">// Mon r&ocirc;le</div>
          <h2 class="section-title reveal" style="margin-bottom:1.6rem">Ce que j&apos;ai<br>r&eacute;alis&eacute;</h2>
          <div class="about-blocks">
            {% for block in about_blocks %}
            <div class="about-block reveal{% if loop.index <= 3 %} reveal-delay-{{ loop.index }}{% endif %}">
              <div class="about-block-title">
                <span class="about-block-dot" style="background:var(--{{ block.slug }})"></span>
                {{ block.title }}
              </div>
              <p>{{ block.description }}</p>
            </div>
            {% endfor %}
          </div>
        </div>

        <div class="tech-panel reveal">
          <div class="tech-panel-title">// Stack technique</div>
          <div class="tech-items">
            {% for item in tech_stack %}
            <div class="tech-item">
              <span class="tech-icon">{{ item.icon | safe }}</span>
              <div class="tech-info">
                <div class="tech-name">{{ item.name }}</div>
                <div class="tech-role">{{ item.role }}</div>
              </div>
            </div>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
  </section>

  <footer>
    <div class="wrap">
      <div class="footer-left">
        <strong>Younes Hachami</strong> &middot; Projet Data Visualisation Multi-Sectorielle &middot; {{ project_year }}
      </div>
      <div class="footer-right">
        <a href="#dashboards">Dashboards</a>
        <a href="#about">&Agrave; propos</a>
        <a href="{{ github_url }}" target="_blank" rel="noreferrer">GitHub &rarr;</a>
      </div>
    </div>
  </footer>
</div>
<script>
const reveals = document.querySelectorAll('.reveal');
const observer = new IntersectionObserver((entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add('visible');
    }
  });
}, { threshold: 0.12 });
reveals.forEach((element) => observer.observe(element));
</script>
</body>
</html>
"""

def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


configure_logging()

def load_local_solar_data() -> pd.DataFrame:
    solar_directory = Path(__file__).resolve().parent / "preprocessing" / "solar_data"
    return preprocess_solar_data(solar_directory)


DATASET_LOADERS: dict[str, DataLoader] = {
    "banking": load_banking_data,
    "solar": load_solar_data,
    "insurance": load_insurance_data,
}
DATASET_FALLBACK_LOADERS: dict[str, DataLoader] = {
    "solar": load_local_solar_data,
}
DATASET_REGISTRY = DatasetRegistry(DATASET_LOADERS, fallback_loaders=DATASET_FALLBACK_LOADERS)


def load_application_data(*, refresh_if_unavailable: bool = False) -> dict[str, DatasetState]:
    return DATASET_REGISTRY.snapshot(refresh_if_unavailable=refresh_if_unavailable)


def _build_status_lines(dataset_states: dict[str, DatasetState]) -> list[str]:
    lines: list[str] = []
    for key in ["banking", "solar", "insurance"]:
        state = dataset_states[key]
        if state.error_message and not state.dataframe.empty:
            lines.append(
                f"{state.name}: {len(state.dataframe)} lignes en cache (MongoDB en reprise: {state.error_message})"
            )
        elif state.error_message:
            lines.append(f"{state.name}: indisponible ({state.error_message})")
        else:
            lines.append(f"{state.name}: {len(state.dataframe)} lignes charg\u00e9es depuis MongoDB")
    return lines


def _build_dataframe_provider(name: str, *, refresh_if_unavailable: bool) -> Callable[[], pd.DataFrame]:
    def _provider() -> pd.DataFrame:
        return DATASET_REGISTRY.get(name, refresh_if_unavailable=refresh_if_unavailable).dataframe

    return _provider


def _build_error_provider(name: str, *, refresh_if_unavailable: bool) -> Callable[[], str | None]:
    def _provider() -> str | None:
        return DATASET_REGISTRY.get(name, refresh_if_unavailable=refresh_if_unavailable).error_message

    return _provider


def register_navigation_routes(server: Flask) -> None:
    github_url = os.getenv("PROJECT_GITHUB_URL", "https://github.com/younesda/examen_dataviz_m2")
    cards = [
        {
            "slug": "banking",
            "icon": '<i class="fa-solid fa-landmark"></i>',
            "sector": "Secteur bancaire",
            "title": "Dashboard Bancaire",
            "href": "/dashboard.html",
            "new_tab": True,
            "description": "Analyse du positionnement des banques au S\u00e9n\u00e9gal avec bilan, emplois, ressources, fonds propres, ratios financiers et lecture BCEAO.",
            "tags": ["KPI financiers", "Comparaison", "BCEAO", "Export PDF"],
        },
        {
            "slug": "energy",
            "icon": '<i class="fa-solid fa-solar-panel"></i>',
            "sector": "\u00c9nergie solaire",
            "title": "Dashboard \u00c9nerg\u00e9tique",
            "href": "/solar/",
            "new_tab": True,
            "description": "Suivi de performance solaire avec production, rendement, irradiation, puissance AC/DC et variables thermiques sur une interface d\u00e9di\u00e9e.",
            "tags": ["Production", "Rendement", "AC/DC", "Thermique"],
        },
        {
            "slug": "insurance",
            "icon": '<i class="fa-solid fa-umbrella"></i>',
            "sector": "Assurance",
            "title": "Dashboard Assurance",
            "href": "/insurance/",
            "new_tab": True,
            "description": "Analyse multipages du portefeuille assurance autour des primes, sinistres, loss ratio, fr\u00e9quence, s\u00e9v\u00e9rit\u00e9 et rentabilit\u00e9.",
            "tags": ["Loss ratio", "Portefeuille", "Sinistres", "Multi-pages"],
        },
    ]
    hero_meta = [
        {"label": "Secteurs couverts", "value": "3 dashboards"},
        {"label": "Stack technique", "value": "Flask \u00b7 Dash \u00b7 MongoDB"},
        {"label": "Source donn\u00e9es", "value": "BCEAO \u00b7 Terrain"},
    ]
    about_blocks = [
        {
            "slug": "banking",
            "title": "Projet Bancaire",
            "description": "Collecte et centralisation des donn\u00e9es BCEAO, nettoyage, structuration et harmonisation. R\u00e9alisation d\u2019un dashboard interactif avec filtres dynamiques, comparaison inter-bancaire et visualisation des grands indicateurs financiers.",
        },
        {
            "slug": "energy",
            "title": "Projet \u00c9nerg\u00e9tique",
            "description": "Organisation des donn\u00e9es solaires, d\u00e9finition des indicateurs de performance et construction de visualisations autour de la production, de l\u2019irradiation, de la puissance AC/DC et des variables thermiques.",
        },
        {
            "slug": "insurance",
            "title": "Projet Assurance",
            "description": "Pr\u00e9paration des donn\u00e9es, d\u00e9finition des KPI m\u00e9tiers comme les primes, sinistres, loss ratio, fr\u00e9quence et s\u00e9v\u00e9rit\u00e9, puis mise en place d\u2019une interface multipages avec filtres partag\u00e9s.",
        },
        {
            "slug": "gold",
            "title": "Int\u00e9gration Globale",
            "description": "Int\u00e9gration de l\u2019ensemble dans une application commune Flask + Dash + MongoDB afin de proposer une navigation unifi\u00e9e et des outils d\u2019aide \u00e0 la d\u00e9cision adapt\u00e9s \u00e0 chaque domaine.",
        },
    ]
    tech_stack = [
        {"icon": '<i class="fa-brands fa-python"></i>', "name": "Python", "role": "Langage principal"},
        {"icon": '<i class="fa-solid fa-flask"></i>', "name": "Flask", "role": "Serveur web \u00b7 navigation"},
        {"icon": '<i class="fa-solid fa-chart-pie"></i>', "name": "Dash / Plotly", "role": "Dashboards interactifs"},
        {"icon": '<i class="fa-solid fa-database"></i>', "name": "MongoDB", "role": "Base de donn\u00e9es"},
        {"icon": '<i class="fa-solid fa-table-columns"></i>', "name": "Pandas", "role": "Traitement des donn\u00e9es"},
        {"icon": '<i class="fa-brands fa-html5"></i>', "name": "HTML / CSS", "role": "Design \u00b7 UX/UI"},
    ]

    @server.route("/")
    def home() -> str:
        dataset_states = load_application_data(refresh_if_unavailable=False)

        def _format_count(value: int) -> str:
            return f"{value:,}".replace(",", " ")

        hero_stats = [
            {"value": _format_count(len(dataset_states["banking"].dataframe)), "label": "Lignes banking"},
            {"value": _format_count(len(dataset_states["solar"].dataframe)), "label": "Lignes solaire"},
            {"value": _format_count(len(dataset_states["insurance"].dataframe)), "label": "Lignes insurance"},
            {"value": str(len(cards)), "label": "Dashboards"},
        ]
        dataset_rows = []
        for dataset in [
            {"key": "banking", "slug": "banking", "label": "banking"},
            {"key": "solar", "slug": "energy", "label": "solar"},
            {"key": "insurance", "slug": "insurance", "label": "insurance"},
        ]:
            state = dataset_states[dataset["key"]]
            if state.error_message and not state.dataframe.empty:
                status = "Cache local actif"
            elif state.error_message:
                status = "Source indisponible"
            else:
                status = "MongoDB \u2713"
            dataset_rows.append({
                "slug": dataset["slug"],
                "label": dataset["label"],
                "status": status,
            })

        return render_template_string(
            HOME_TEMPLATE,
            cards=cards,
            hero_meta=hero_meta,
            hero_stats=hero_stats,
            dataset_rows=dataset_rows,
            about_blocks=about_blocks,
            tech_stack=tech_stack,
            github_url=github_url,
            project_year=2025,
        )

    @server.route("/banking")
    def banking_redirect() -> object:
        return redirect("/dashboard.html")

    @server.route("/dashboard.html")
    def banking_html_dashboard() -> object:
        return send_from_directory(DASHBOARDS_DIR, "dashboard.html")

    @server.route("/solar")
    def solar_redirect() -> object:
        return redirect("/solar/")

    @server.route("/solar/")
    def solar_page() -> str:
        state = DATASET_REGISTRY.get("solar", refresh_if_unavailable=True)
        return render_solar_observatory_page(state.dataframe, state.error_message)

    @server.route("/solar-assets/<path:filename>")
    def solar_assets(filename: str):
        return send_from_directory(ASSETS_DIR, filename)

    @server.route("/insurance")
    def insurance_redirect() -> object:
        return redirect("/insurance/")


def create_flask_server() -> Flask:
    server = Flask(__name__)
    register_navigation_routes(server)
    return server


def mount_dashboards(server: Flask) -> dict[str, object]:
    return {
        "banking": create_banking_dashboard(
            server,
            callback_dataframe_provider=_build_dataframe_provider("banking", refresh_if_unavailable=True),
            error_provider=_build_error_provider("banking", refresh_if_unavailable=True),
            layout_dataframe_provider=_build_dataframe_provider("banking", refresh_if_unavailable=True),
        ),
        "insurance": create_insurance_dashboard(
            server,
            callback_dataframe_provider=_build_dataframe_provider("insurance", refresh_if_unavailable=True),
            error_provider=_build_error_provider("insurance", refresh_if_unavailable=True),
            layout_dataframe_provider=_build_dataframe_provider("insurance", refresh_if_unavailable=True),
        ),
    }


flask_server = create_flask_server()
DASH_APPS = mount_dashboards(flask_server)
server = flask_server


if __name__ == "__main__":
    LOGGER.info("Starting Flask navigation server with independent Dash dashboards.")
    flask_server.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8050")),
        debug=os.getenv("DASH_DEBUG", "false").lower() == "true",
    )



