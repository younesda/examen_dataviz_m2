(function () {
  const ALL_VALUE = '__all__';
  const charts = {};
  let observerStarted = false;
  let lastSignature = '';

  function hasSolarRoot() {
    return Boolean(document.querySelector('.solar-observatory-root'));
  }

  function setBodyState() {
    document.body.classList.toggle('solar-observatory-body', hasSolarRoot());
  }

  function updateClock() {
    const clock = document.getElementById('live-time');
    if (!clock) {
      return;
    }
    clock.textContent = new Date().toTimeString().slice(0, 8);
  }

  function parsePayload() {
    const payloadElement = document.getElementById('solar-observatory-payload');
    if (!payloadElement) {
      return null;
    }

    try {
      return JSON.parse(payloadElement.textContent || '{}');
    } catch (error) {
      console.error('Unable to parse solar observatory payload.', error);
      return null;
    }
  }

  function numericValue(value) {
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  }

  function average(records, key) {
    const values = records.map((record) => numericValue(record[key])).filter((value) => value !== null);
    if (!values.length) {
      return 0;
    }
    return values.reduce((total, value) => total + value, 0) / values.length;
  }

  function maximum(records, key) {
    const values = records.map((record) => numericValue(record[key])).filter((value) => value !== null);
    if (!values.length) {
      return 0;
    }
    return Math.max(...values);
  }

  function formatDisplayDate(dateString) {
    const date = new Date(`${dateString}T00:00:00`);
    const months = ['JAN', 'FEV', 'MAR', 'AVR', 'MAI', 'JUN', 'JUL', 'AOU', 'SEP', 'OCT', 'NOV', 'DEC'];
    const day = String(date.getDate()).padStart(2, '0');
    return `${day} ${months[date.getMonth()] || ''} ${date.getFullYear()}`.trim();
  }

  function formatPeriod(records) {
    if (!records.length) {
      return 'PERIODE INDISPONIBLE';
    }
    return `${formatDisplayDate(records[0].date_iso)} -> ${formatDisplayDate(records[records.length - 1].date_iso)}`;
  }

  function humanizeSource(source) {
    return String(source || 'ac_dc_ratio')
      .replaceAll('_', ' ')
      .split(' ')
      .filter(Boolean)
      .map((part) => (part.length <= 3 ? part.toUpperCase() : part.charAt(0).toUpperCase() + part.slice(1)))
      .join(' ');
  }


  function ensureTemporalControls(payload) {
    const records = Array.isArray(payload.records) ? payload.records.slice() : [];
    const monthSelect = document.getElementById('solar-month-filter');
    const startInput = document.getElementById('solar-start-date-filter');
    const endInput = document.getElementById('solar-end-date-filter');

    if (!monthSelect || !startInput || !endInput) {
      return;
    }

    const monthEntries = Array.from(
      new Map(records.map((record) => [record.period_key, record.month_digest])).entries(),
    ).sort((left, right) => left[0].localeCompare(right[0]));
    const monthSignature = monthEntries.map(([value, label]) => `${value}:${label}`).join('|');
    if (monthSelect.dataset.signature !== monthSignature) {
      const currentValue = monthSelect.value || ALL_VALUE;
      monthSelect.innerHTML = '';

      const defaultOption = document.createElement('option');
      defaultOption.value = ALL_VALUE;
      defaultOption.textContent = 'Tous les mois';
      monthSelect.appendChild(defaultOption);

      monthEntries.forEach(([value, label]) => {
        const option = document.createElement('option');
        option.value = value;
        option.textContent = label;
        monthSelect.appendChild(option);
      });

      monthSelect.value = monthEntries.some(([value]) => value === currentValue) ? currentValue : ALL_VALUE;
      monthSelect.dataset.signature = monthSignature;
    }

    const dates = records.map((record) => record.date_iso).filter(Boolean).sort();
    if (!dates.length) {
      return;
    }

    const minDate = dates[0];
    const maxDate = dates[dates.length - 1];
    startInput.min = minDate;
    startInput.max = maxDate;
    endInput.min = minDate;
    endInput.max = maxDate;

    if (!startInput.value || startInput.value < minDate || startInput.value > maxDate) {
      startInput.value = minDate;
    }
    if (!endInput.value || endInput.value < minDate || endInput.value > maxDate) {
      endInput.value = maxDate;
    }
    if (startInput.value > endInput.value) {
      endInput.value = startInput.value;
    }
  }

  function computeMetrics(records) {
    if (!records.length) {
      return {
        telemetryCount: '0',
        activeDays: '0',
        activeScopes: '0',
        avgAcPower: '0.0 kW',
        avgEfficiency: '0.0%',
        avgIrradiation: '0.00',
        avgDailyYield: '0.0',
        avgAmbientTemperature: '0.0 C',
        avgModuleTemperature: '0.0 C',
        peakAcPower: '0.0 kW',
        periodLabel: 'PERIODE INDISPONIBLE',
        sourceLabel: 'AC/DC Ratio',
      };
    }

    const telemetryCount = records.reduce((total, record) => total + Number(record.observations || 0), 0);
    const activeScopes = new Set(records.map((record) => record.company).filter(Boolean)).size;

    return {
      telemetryCount: String(telemetryCount),
      activeDays: String(records.length),
      activeScopes: String(activeScopes),
      avgAcPower: `${average(records, 'ac_power').toFixed(1)} kW`,
      avgEfficiency: `${average(records, 'efficiency').toFixed(1)}%`,
      avgIrradiation: average(records, 'irradiation').toFixed(2),
      avgDailyYield: average(records, 'daily_yield').toFixed(1),
      avgAmbientTemperature: `${average(records, 'ambient_temperature').toFixed(1)} C`,
      avgModuleTemperature: `${average(records, 'module_temperature').toFixed(1)} C`,
      peakAcPower: `${maximum(records, 'ac_power').toFixed(1)} kW`,
      periodLabel: formatPeriod(records),
      sourceLabel: humanizeSource(records[0].source),
    };
  }

  function currentRecords(payload) {
    const scopeSelect = document.getElementById('solar-company-filter');
    const monthSelect = document.getElementById('solar-month-filter');
    const startInput = document.getElementById('solar-start-date-filter');
    const endInput = document.getElementById('solar-end-date-filter');
    const selectedScope = scopeSelect ? scopeSelect.value : ALL_VALUE;
    const selectedMonth = monthSelect ? monthSelect.value : ALL_VALUE;
    const startDate = startInput ? startInput.value : '';
    const endDate = endInput ? endInput.value : '';
    let records = Array.isArray(payload.records) ? payload.records.slice() : [];

    if (selectedScope && selectedScope !== ALL_VALUE) {
      if (selectedScope.startsWith('company::')) {
        const company = selectedScope.replace('company::', '');
        records = records.filter((record) => record.company === company);
      } else if (selectedScope.startsWith('period::')) {
        const period = selectedScope.replace('period::', '');
        records = records.filter((record) => record.period_key === period);
      }
    }

    if (selectedMonth && selectedMonth !== ALL_VALUE) {
      records = records.filter((record) => record.period_key === selectedMonth);
    }

    if (startDate) {
      records = records.filter((record) => record.date_iso >= startDate);
    }

    if (endDate) {
      records = records.filter((record) => record.date_iso <= endDate);
    }

    return records;
  }

  function setText(id, value) {
    const element = document.getElementById(id);
    if (element) {
      element.textContent = value;
    }
  }

  function updateSummary(payload, records) {
    const metrics = computeMetrics(records);
    setText('mongo-status-label', payload.status_label || 'MONGODB CONNECTE');
    setText('hero-date', metrics.periodLabel);
    setText('hero-badge-records', `${metrics.telemetryCount} points horaires`);
    setText('hero-badge-months', `${metrics.activeDays} jours`);
    setText('hero-badge-source', metrics.sourceLabel);
    setText('side-period-title', metrics.periodLabel);
    setText('side-source-title', metrics.sourceLabel);
    setText('s-releves', metrics.telemetryCount);
    setText('s-mois', metrics.activeScopes);
    setText('s-eff', metrics.avgAcPower);
    setText('s-growth', metrics.avgEfficiency);
    setText('temp-avg-value', metrics.avgIrradiation);
    setText('humidity-avg-value', metrics.avgDailyYield);
    setText('wind-avg-value', metrics.avgAmbientTemperature);
    setText('pressure-avg-value', metrics.avgModuleTemperature);
  }

  function buildMonthlyBuckets(records) {
    const map = new Map();
    records.forEach((record) => {
      if (!map.has(record.period_key)) {
        map.set(record.period_key, {
          label: record.month_digest,
          days: 0,
          observations: 0,
          acPowerTotal: 0,
          dailyYieldTotal: 0,
          irradiationTotal: 0,
          efficiencyTotal: 0,
          efficiencyCount: 0,
        });
      }
      const bucket = map.get(record.period_key);
      bucket.days += 1;
      bucket.observations += Number(record.observations || 0);
      bucket.acPowerTotal += Number(record.ac_power || 0);
      bucket.dailyYieldTotal += Number(record.daily_yield || 0);
      bucket.irradiationTotal += Number(record.irradiation || 0);

      const efficiency = numericValue(record.efficiency);
      if (efficiency !== null) {
        bucket.efficiencyTotal += efficiency;
        bucket.efficiencyCount += 1;
      }
    });

    return Array.from(map.entries())
      .sort((left, right) => left[0].localeCompare(right[0]))
      .map(([, bucket]) => ({
        label: bucket.label,
        days: bucket.days,
        observations: bucket.observations,
        avgAcPower: bucket.days ? bucket.acPowerTotal / bucket.days : 0,
        avgDailyYield: bucket.days ? bucket.dailyYieldTotal / bucket.days : 0,
        avgIrradiation: bucket.days ? bucket.irradiationTotal / bucket.days : 0,
        avgEfficiency: bucket.efficiencyCount ? bucket.efficiencyTotal / bucket.efficiencyCount : 0,
      }));
  }

  function formatNumber(value, digits, suffix = '') {
    const number = numericValue(value);
    if (number === null) {
      return '—';
    }
    return `${number.toFixed(digits)}${suffix}`;
  }

  function renderTables(records) {
    const rawBody = document.getElementById('rawTableBody');
    const digestBody = document.getElementById('digestBody');
    if (!rawBody || !digestBody) {
      return;
    }

    rawBody.innerHTML = '';
    digestBody.innerHTML = '';

    records.slice(-20).reverse().forEach((record) => {
      const row = document.createElement('tr');
      const efficiency = numericValue(record.efficiency);
      const efficiencyClass = efficiency !== null && efficiency >= 92 ? 'td-pos' : efficiency !== null && efficiency < 88 ? 'td-neg' : '';
      row.innerHTML = `
        <td class="td-date">${record.date_iso}</td>
        <td>${record.company}</td>
        <td>${formatNumber(record.ac_power, 1, ' kW')}</td>
        <td>${formatNumber(record.dc_power, 1, ' kW')}</td>
        <td>${formatNumber(record.irradiation, 3, '')}</td>
        <td>${formatNumber(record.daily_yield, 1, '')}</td>
        <td class="td-eff ${efficiencyClass}">${formatNumber(record.efficiency, 1, '%')}</td>`;
      rawBody.appendChild(row);
    });

    buildMonthlyBuckets(records).forEach((bucket) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td class="td-date">${bucket.label}</td>
        <td>${bucket.days}</td>
        <td>${bucket.avgAcPower.toFixed(1)} kW</td>
        <td>${bucket.avgDailyYield.toFixed(1)}</td>`;
      digestBody.appendChild(row);
    });
  }

  function destroyChart(id) {
    if (charts[id]) {
      charts[id].destroy();
      delete charts[id];
    }
  }

  function createChart(id, config) {
    const canvas = document.getElementById(id);
    if (!canvas || !window.Chart) {
      return;
    }
    destroyChart(id);
    charts[id] = new window.Chart(canvas, config);
  }

  function setChartDefaults() {
    if (!window.Chart) {
      return;
    }
    window.Chart.defaults.color = '#4A6080';
    window.Chart.defaults.font.family = "'IBM Plex Mono', monospace";
    window.Chart.defaults.font.size = 10;
  }

  function buildScatterPoints(records, xKey, yKey) {
    return records
      .map((record) => ({
        x: numericValue(record[xKey]),
        y: numericValue(record[yKey]),
        efficiency: numericValue(record.efficiency),
      }))
      .filter((point) => point.x !== null && point.y !== null);
  }

  function renderCharts(records) {
    if (!window.Chart) {
      return;
    }

    setChartDefaults();
    const gridColor = 'rgba(255,200,60,0.06)';
    const axisColor = 'rgba(255,200,60,0.15)';
    const dailyLabels = records.map((record) => record.date_axis);
    const monthly = buildMonthlyBuckets(records);
    const thermalModulePoints = buildScatterPoints(records, 'module_temperature', 'efficiency');
    const thermalAmbientPoints = buildScatterPoints(records, 'ambient_temperature', 'efficiency');
    const irradiationScatterPoints = buildScatterPoints(records, 'irradiation', 'ac_power');
    const irradiationScatterHigh = irradiationScatterPoints.filter((point) => point.efficiency !== null && point.efficiency >= 92);
    const irradiationScatterStable = irradiationScatterPoints.filter((point) => point.efficiency === null || (point.efficiency >= 88 && point.efficiency < 92));
    const irradiationScatterLow = irradiationScatterPoints.filter((point) => point.efficiency !== null && point.efficiency < 88);

    createChart('dailyChart', {
      type: 'line',
      data: {
        labels: dailyLabels,
        datasets: [
          {
            label: 'Puissance AC',
            data: records.map((record) => record.ac_power),
            borderColor: '#FFC83C',
            backgroundColor: 'rgba(255,200,60,0.10)',
            borderWidth: 1.6,
            pointRadius: 0,
            tension: 0.35,
            fill: true,
          },
          {
            label: 'Puissance DC',
            data: records.map((record) => record.dc_power),
            borderColor: '#1AD4CC',
            backgroundColor: 'transparent',
            borderWidth: 1.4,
            pointRadius: 0,
            tension: 0.35,
          },
          {
            label: 'Irradiation',
            data: records.map((record) => record.irradiation),
            borderColor: '#8B6DFF',
            backgroundColor: 'transparent',
            borderWidth: 1.2,
            pointRadius: 0,
            tension: 0.35,
            yAxisID: 'y2',
            borderDash: [4, 4],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: 'index', intersect: false },
        plugins: {
          legend: { display: true, position: 'top', labels: { usePointStyle: true, boxWidth: 8, color: '#4A6080' } },
          tooltip: {
            backgroundColor: '#0C1420',
            borderColor: 'rgba(255,200,60,0.3)',
            borderWidth: 1,
            titleColor: '#FFC83C',
            bodyColor: '#8BAFD4',
            padding: 10,
          },
        },
        scales: {
          x: { grid: { color: gridColor }, ticks: { maxTicksLimit: 10, color: '#4A6080' }, border: { color: axisColor } },
          y: { title: { display: true, text: 'Puissance (kW)', color: '#4A6080' }, grid: { color: gridColor }, ticks: { color: '#4A6080' }, border: { color: axisColor }, position: 'left' },
          y2: { title: { display: true, text: 'Irradiation', color: '#8B6DFF' }, grid: { display: false }, ticks: { color: '#8B6DFF' }, border: { color: axisColor }, position: 'right' },
        },
      },
    });

    createChart('monthlyChart', {
      type: 'bar',
      data: {
        labels: monthly.map((bucket) => bucket.label.split(' ')[0]),
        datasets: [
          {
            label: 'Puissance AC',
            data: monthly.map((bucket) => Number(bucket.avgAcPower.toFixed(1))),
            backgroundColor: 'rgba(255,200,60,0.55)',
            borderColor: '#FFC83C',
            borderWidth: 1,
            borderRadius: 4,
          },
          {
            label: 'Yield journalier',
            data: monthly.map((bucket) => Number(bucket.avgDailyYield.toFixed(1))),
            type: 'line',
            borderColor: '#1AD4CC',
            backgroundColor: 'transparent',
            borderWidth: 2,
            pointRadius: 3,
            tension: 0.35,
            yAxisID: 'y2',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: true, position: 'top', labels: { usePointStyle: true, boxWidth: 8, color: '#4A6080' } } },
        scales: {
          x: { grid: { color: gridColor }, ticks: { color: '#4A6080' }, border: { color: axisColor } },
          y: { title: { display: true, text: 'AC (kW)', color: '#4A6080' }, grid: { color: gridColor }, ticks: { color: '#4A6080' }, border: { color: axisColor } },
          y2: { title: { display: true, text: 'Yield journalier', color: '#1AD4CC' }, grid: { display: false }, ticks: { color: '#1AD4CC' }, border: { color: axisColor }, position: 'right' },
        },
      },
    });

    createChart('thermalChart', {
      type: 'scatter',
      data: {
        datasets: [
          {
            label: 'Module / rendement',
            data: thermalModulePoints.map((point) => ({ x: point.x, y: point.y })),
            backgroundColor: 'rgba(255,200,60,0.45)',
            pointRadius: 3,
          },
          {
            label: 'Ambiante / rendement',
            data: thermalAmbientPoints.map((point) => ({ x: point.x, y: point.y })),
            backgroundColor: 'rgba(26,212,204,0.40)',
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: true, position: 'top', labels: { usePointStyle: true, boxWidth: 8, color: '#4A6080' } } },
        scales: {
          x: { title: { display: true, text: 'Temp\u00e9rature (C)', color: '#4A6080', font: { size: 10 } }, grid: { color: gridColor }, ticks: { color: '#4A6080' }, border: { color: axisColor } },
          y: { title: { display: true, text: 'Rendement (%)', color: '#4A6080', font: { size: 10 } }, grid: { color: gridColor }, ticks: { color: '#4A6080' }, border: { color: axisColor } },
        },
      },
    });

    createChart('meteoChart', {
      type: 'line',
      data: {
        labels: dailyLabels,
        datasets: [
          {
            label: 'Temp\u00e9rature ambiante',
            data: records.map((record) => record.ambient_temperature),
            borderColor: '#1AD4CC',
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.35,
            backgroundColor: 'rgba(26,212,204,0.08)',
            fill: true,
          },
          {
            label: 'Temp\u00e9rature module',
            data: records.map((record) => record.module_temperature),
            borderColor: '#FF4D6A',
            borderWidth: 1.5,
            pointRadius: 0,
            tension: 0.35,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: true, position: 'top', labels: { usePointStyle: true, boxWidth: 8, color: '#4A6080' } } },
        scales: {
          x: { grid: { color: gridColor }, ticks: { maxTicksLimit: 6, color: '#4A6080' }, border: { color: axisColor } },
          y: { title: { display: true, text: 'Temp\u00e9rature (C)', color: '#4A6080' }, grid: { color: gridColor }, ticks: { color: '#4A6080' }, border: { color: axisColor } },
        },
      },
    });

    createChart('scatterChart', {
      type: 'scatter',
      data: {
        datasets: [
          {
            label: 'Rendement \u00e9lev\u00e9',
            data: irradiationScatterHigh.map((point) => ({ x: point.x, y: point.y })),
            backgroundColor: 'rgba(61,255,160,0.5)',
            pointRadius: 4,
          },
          {
            label: 'Rendement stable',
            data: irradiationScatterStable.map((point) => ({ x: point.x, y: point.y })),
            backgroundColor: 'rgba(255,200,60,0.45)',
            pointRadius: 4,
          },
          {
            label: 'Sous surveillance',
            data: irradiationScatterLow.map((point) => ({ x: point.x, y: point.y })),
            backgroundColor: 'rgba(255,77,106,0.5)',
            pointRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: true, position: 'top', labels: { usePointStyle: true, boxWidth: 8, color: '#4A6080' } },
          tooltip: {
            backgroundColor: '#0C1420',
            borderColor: 'rgba(255,200,60,0.3)',
            borderWidth: 1,
            titleColor: '#FFC83C',
            bodyColor: '#8BAFD4',
            padding: 10,
            callbacks: {
              label: (context) => `Irrad: ${context.raw.x.toFixed(3)} | AC: ${context.raw.y.toFixed(1)} kW`,
            },
          },
        },
        scales: {
          x: {
            title: { display: true, text: 'Irradiation', color: '#4A6080', font: { size: 10 } },
            grid: { color: gridColor },
            ticks: { color: '#4A6080' },
            border: { color: axisColor },
          },
          y: {
            title: { display: true, text: 'Puissance AC (kW)', color: '#4A6080', font: { size: 10 } },
            grid: { color: gridColor },
            ticks: { color: '#4A6080' },
            border: { color: axisColor },
          },
        },
      },
    });
  }

  function syncSolar() {
    setBodyState();
    if (!hasSolarRoot()) {
      lastSignature = '';
      return;
    }

    const payload = parsePayload();
    if (!payload) {
      return;
    }

    ensureTemporalControls(payload);
    const records = currentRecords(payload);
    const scopeSelect = document.getElementById('solar-company-filter');
    const monthSelect = document.getElementById('solar-month-filter');
    const startInput = document.getElementById('solar-start-date-filter');
    const endInput = document.getElementById('solar-end-date-filter');
    const firstRecord = records.length ? records[0].date_iso : '';
    const lastRecord = records.length ? records[records.length - 1].date_iso : '';
    const signature = JSON.stringify({
      selectedScope: scopeSelect ? scopeSelect.value : ALL_VALUE,
      selectedMonth: monthSelect ? monthSelect.value : ALL_VALUE,
      startDate: startInput ? startInput.value : '',
      endDate: endInput ? endInput.value : '',
      status: payload.status_label || '',
      count: records.length,
      first: firstRecord,
      last: lastRecord,
    });

    if (signature === lastSignature) {
      return;
    }

    lastSignature = signature;
    updateSummary(payload, records);
    renderTables(records);
    renderCharts(records);
  }

  function setPrintState(isPrinting) {
    document.body.classList.toggle('solar-pdf-export-active', Boolean(isPrinting));
  }

  const SOLAR_EXPORT_COLS = [
    {h: 'Date',              k: 'date_iso'},
    {h: 'Pays',              k: 'company'},
    {h: 'Mois',              k: 'month_label'},
    {h: 'Periode',           k: 'period_key'},
    {h: 'Observations',      k: 'observations'},
    {h: 'AC_Power_kW',       k: 'ac_power'},
    {h: 'DC_Power_kW',       k: 'dc_power'},
    {h: 'Irradiation',       k: 'irradiation'},
    {h: 'Daily_Yield',       k: 'daily_yield'},
    {h: 'Efficacite_pct',    k: 'efficiency'},
    {h: 'Temp_Ambiante_C',   k: 'ambient_temperature'},
    {h: 'Temp_Module_C',     k: 'module_temperature'},
  ];

  function _solarExportSuffix() {
    const scope = document.getElementById('solar-company-filter');
    const s = scope ? scope.value : '';
    if (s && s !== '__all__') {
      return '_' + s.replace(/[:\/\s]+/g, '_');
    }
    return '';
  }

  function exportSolarCSV() {
    const records = currentRecords(parsePayload());
    const rows = [SOLAR_EXPORT_COLS.map(c => c.h).join(';')];
    records.forEach(r => {
      rows.push(SOLAR_EXPORT_COLS.map(c => {
        const v = r[c.k];
        return (v !== null && v !== undefined) ? String(v).replace(/;/g, ',') : '';
      }).join(';'));
    });
    const blob = new Blob(['\uFEFF' + rows.join('\r\n')], {type: 'text/csv;charset=utf-8;'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'solar_observatory' + _solarExportSuffix() + '.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  function exportSolarXLSX() {
    if (typeof XLSX === 'undefined') { alert('SheetJS non disponible'); return; }
    const records = currentRecords(parsePayload());
    const rows = [SOLAR_EXPORT_COLS.map(c => c.h)];
    records.forEach(r => {
      rows.push(SOLAR_EXPORT_COLS.map(c => {
        const v = r[c.k];
        return (v !== null && v !== undefined) ? v : '';
      }));
    });
    const ws = XLSX.utils.aoa_to_sheet(rows);
    ws['!cols'] = SOLAR_EXPORT_COLS.map(c => ({wch: 16}));
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Solar Data');
    XLSX.writeFile(wb, 'solar_observatory' + _solarExportSuffix() + '.xlsx');
  }

  function bindExportButton() {
    const button = document.getElementById('solar-export-pdf-button');
    if (!button || button.dataset.bound === 'true') {
      return;
    }
    button.dataset.bound = 'true';
    button.addEventListener('click', () => {
      setPrintState(true);
      window.print();
      window.setTimeout(() => setPrintState(false), 300);
    });
  }

  function bindExportButtons() {
    const csvBtn = document.getElementById('solar-export-csv-button');
    if (csvBtn && csvBtn.dataset.bound !== 'true') {
      csvBtn.dataset.bound = 'true';
      csvBtn.addEventListener('click', exportSolarCSV);
    }
    const xlsxBtn = document.getElementById('solar-export-excel-button');
    if (xlsxBtn && xlsxBtn.dataset.bound !== 'true') {
      xlsxBtn.dataset.bound = 'true';
      xlsxBtn.addEventListener('click', exportSolarXLSX);
    }
  }

  function bindSelect() {
    const select = document.getElementById('solar-company-filter');
    if (!select || select.dataset.bound === 'true') {
      return;
    }
    select.dataset.bound = 'true';
    select.addEventListener('change', syncSolar);
  }

  function bindTemporalControls() {
    const controls = [
      document.getElementById('solar-month-filter'),
      document.getElementById('solar-start-date-filter'),
      document.getElementById('solar-end-date-filter'),
    ];

    controls.forEach((control) => {
      if (!control || control.dataset.bound === 'true') {
        return;
      }

      control.dataset.bound = 'true';
      control.addEventListener('change', () => {
        const startInput = document.getElementById('solar-start-date-filter');
        const endInput = document.getElementById('solar-end-date-filter');
        if (startInput && endInput && startInput.value && endInput.value && startInput.value > endInput.value) {
          if (control.id === 'solar-end-date-filter') {
            startInput.value = endInput.value;
          } else {
            endInput.value = startInput.value;
          }
        }
        syncSolar();
      });
    });
  }

  function startObserver() {
    if (observerStarted) {
      return;
    }
    observerStarted = true;
    const observer = new MutationObserver(() => {
      setBodyState();
      bindExportButton();
      bindExportButtons();
      bindSelect();
      bindTemporalControls();
      syncSolar();
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true });
  }

  window.addEventListener('beforeprint', () => setPrintState(true));
  window.addEventListener('afterprint', () => setPrintState(false));

  document.addEventListener('DOMContentLoaded', () => {
    updateClock();
    setInterval(updateClock, 1000);
    bindExportButton();
    bindExportButtons();
    bindSelect();
    bindTemporalControls();
    syncSolar();
    startObserver();
    setInterval(() => {
      bindExportButton();
      bindExportButtons();
      bindSelect();
      bindTemporalControls();
      syncSolar();
    }, 1500);
  });
})();

