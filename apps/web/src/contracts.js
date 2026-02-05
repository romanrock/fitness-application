export const overviewContract = {
  weekLabel: 'Jan 17 - Jan 23',
  allTimeCards: [
    { id: 'run', label: 'Running', value: '412.5 km • 42 runs', accent: 'run' },
    { id: 'golf', label: 'Golf', value: '18 rounds', accent: 'golf' },
    { id: 'walk', label: 'Walking', value: '48.2 km • 12 walks', accent: 'neutral' }
  ],
  weeklyCards: [
    { id: 'run', label: 'Running', value: '12.5 km • 4 runs', accent: 'run' },
    { id: 'golf', label: 'Golf', value: '—', accent: 'golf' },
    { id: 'walk', label: 'Walking', value: '—', accent: 'neutral' }
  ],
  insights: [
    { id: 'vdot', label: 'VDOT (best 12m)', value: '—', tone: 'neutral', hint: 'Performance-based estimate' },
    { id: 'pace_trend', label: 'Pace trend (12w)', value: '—', tone: 'neutral', hint: 'sec/km per week' },
    { id: 'hr_trend', label: 'HR trend (12w)', value: '—', tone: 'neutral', hint: 'bpm per week' },
    { id: 'eff_trend', label: 'Efficiency trend (12w)', value: '—', tone: 'neutral', hint: 'index per week' },
    { id: 'decoupling', label: 'Decoupling (28d)', value: '—', tone: 'neutral', hint: 'lower is better' },
    { id: 'monotony', label: 'Monotony (wk)', value: '—', tone: 'neutral', hint: 'Higher = less variation' },
    { id: 'strain', label: 'Strain (wk)', value: '—', tone: 'neutral', hint: 'Monotony × volume' },
    { id: 'volume', label: 'Run volume', value: '—', tone: 'neutral', hint: '7d vs 28d' },
    { id: 'fatigue_load', label: 'Weekly fatigue (4w avg)', value: '—', tone: 'neutral', hint: 'Load = moving_s × avg HR' },
    { id: 'recovery_index', label: 'Recovery index (28d)', value: '—', tone: 'neutral', hint: 'Median efficiency vs best (0–100)' },
    { id: 'eff_trend_phr', label: 'Pace/HR efficiency trend', value: '—', tone: 'neutral', hint: 'Higher is better' }
  ],
  performance: [
    { id: 'pb_5k_all', label: 'PB 5K (all time)', value: '—', tone: 'neutral', hint: '—' },
    { id: 'pb_10k_all', label: 'PB 10K (all time)', value: '—', tone: 'neutral', hint: '—' },
    { id: 'pb_5k_12m', label: 'PB 5K (12m)', value: '—', tone: 'neutral', hint: '—' },
    { id: 'pb_10k_12m', label: 'PB 10K (12m)', value: '—', tone: 'neutral', hint: '—' },
    { id: 'est_5k', label: 'Estimated 5K', value: '—', tone: 'neutral', hint: 'Segment-based' },
    { id: 'est_10k', label: 'Estimated 10K', value: '—', tone: 'neutral', hint: 'Segment-based' }
  ]
};

export const activityDetailContract = {
  id: 'run-1',
  type: 'run',
  title: 'Morning Run - City of Edinburgh',
  date: '29 Jan @ 14:00',
  location: 'Edinburgh',
  weather: '5°C',
  heroStats: [
    { label: 'Distance', value: '4.01 km' },
    { label: 'Avg Pace', value: '4:05 /km' },
    { label: 'Moving Time', value: '16:23' },
    { label: 'Elevation', value: '9 m' },
    { label: 'Calories', value: '278' },
    { label: 'Avg HR', value: '162 bpm' }
  ],
  tabs: ['Overview', 'Laps', 'Charts'],
  laps: [
    { lap: 1, time: '4:28.4', distance: '1.00', pace: '4:28' },
    { lap: 2, time: '4:02.2', distance: '1.00', pace: '4:02' },
    { lap: 3, time: '3:57.3', distance: '1.00', pace: '3:57' },
    { lap: 4, time: '3:53.3', distance: '1.00', pace: '3:53' },
    { lap: 5, time: '0:01.8', distance: '0.01', pace: '3:27' }
  ]
};

export const activitiesContract = {
  title: 'Activities',
  filterLabel: 'All activities',
  items: [
    { id: 'run-1', title: 'Morning Run', date: 'Jan 20', stats: ['5.3 km', '32:15'], accent: 'run' },
    { id: 'walk-1', title: 'Evening Walk', date: 'Jan 20', stats: ['4.1 km', '52:08'], accent: 'neutral' }
  ]
};

export const profileContract = {
  name: 'Roman',
  stats: [
    { label: 'Height', value: '183 cm' },
    { label: 'Outer leg', value: '104 cm' },
    { label: 'Inner leg', value: '86 cm' },
    { label: 'Neck', value: '41 cm' },
    { label: 'Chest', value: '103 cm' },
    { label: 'Hips', value: '96 cm' },
    { label: 'Waist', value: '86 cm' },
    { label: 'Belly', value: '90 cm' },
    { label: 'Thigh', value: '56 cm' },
    { label: 'Calves', value: '38 cm' },
    { label: 'Weight', value: '80 kg' },
    { label: 'Born', value: 'April 1983' },
    { label: 'Resting HR', value: '48 bpm' }
  ]
};
