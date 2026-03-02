export interface WorkerData {
  workerId: string;
  name: string;
  gender: string;
  birthYear: number;
  jobType: string;
  startDate: string;
  riskLevel: 'high' | 'low';
  yearlyData: YearlyData[];
  averageSickDays: number;
  frequencyPerYear: number;
  isDauerKrank: boolean;
}

export interface YearlyData {
  year: number;
  daysSickness: number;
  frequencySick: number;
  monthlyBreakdown?: MonthlyData[];
}

export interface MonthlyData {
  month: string;
  days: number;
}

export const mockWorkers: WorkerData[] = [
  {
    workerId: 'W0001',
    name: 'Maxine Mustermann',
    gender: 'Female',
    birthYear: 1986,
    jobType: 'Produktion',
    startDate: '2015-08-21',
    riskLevel: 'low',
    averageSickDays: 12.8,
    frequencyPerYear: 2.8,
    isDauerKrank: false,
    yearlyData: [
      {
        year: 2022,
        daysSickness: 7,
        frequencySick: 3,
        monthlyBreakdown: [
          { month: 'January', days: 2 },
          { month: 'February', days: 0 },
          { month: 'March', days: 3 },
          { month: 'April', days: 2 },
          { month: 'May', days: 0 },
          { month: 'June', days: 0 },
          { month: 'July', days: 0 },
          { month: 'August', days: 0 },
          { month: 'September', days: 0 },
          { month: 'October', days: 0 },
          { month: 'November', days: 0 },
          { month: 'December', days: 0 },
        ]
      },
      {
        year: 2023,
        daysSickness: 19,
        frequencySick: 2,
        monthlyBreakdown: [
          { month: 'January', days: 8 },
          { month: 'February', days: 4 },
          { month: 'March', days: 0 },
          { month: 'April', days: 7 },
          { month: 'May', days: 0 },
          { month: 'June', days: 0 },
          { month: 'July', days: 0 },
          { month: 'August', days: 0 },
          { month: 'September', days: 0 },
          { month: 'October', days: 0 },
          { month: 'November', days: 0 },
          { month: 'December', days: 0 },
        ]
      },
      {
        year: 2024,
        daysSickness: 2,
        frequencySick: 3,
        monthlyBreakdown: [
          { month: 'January', days: 1 },
          { month: 'February', days: 0 },
          { month: 'March', days: 0 },
          { month: 'April', days: 1 },
          { month: 'May', days: 0 },
          { month: 'June', days: 0 },
          { month: 'July', days: 0 },
          { month: 'August', days: 0 },
          { month: 'September', days: 0 },
          { month: 'October', days: 0 },
          { month: 'November', days: 0 },
          { month: 'December', days: 0 },
        ]
      }
    ]
  },
  {
    workerId: 'W0002',
    name: 'Jana Marie',
    gender: 'Female',
    birthYear: 1986,
    jobType: 'Verwaltung',
    startDate: '2022-10-12',
    riskLevel: 'high',
    averageSickDays: 16,
    frequencyPerYear: 3.3,
    isDauerKrank: false,
    yearlyData: [
      { year: 2022, daysSickness: 17, frequencySick: 5 },
      { year: 2023, daysSickness: 16, frequencySick: 4 },
      { year: 2024, daysSickness: 18, frequencySick: 1 }
    ]
  },
  {
    workerId: 'W0003',
    name: 'Silvia Marie',
    gender: 'Female',
    birthYear: 1972,
    jobType: 'Pflege',
    startDate: '2005-09-07',
    riskLevel: 'low',
    averageSickDays: 15.4,
    frequencyPerYear: 2.4,
    isDauerKrank: false,
    yearlyData: [
      { year: 2022, daysSickness: 9, frequencySick: 0 },
      { year: 2023, daysSickness: 6, frequencySick: 2 },
      { year: 2024, daysSickness: 12, frequencySick: 3 }
    ]
  },
  {
    workerId: 'W0004',
    name: 'Anna Carolina',
    gender: 'Female',
    birthYear: 1985,
    jobType: 'Produktion',
    startDate: '2022-07-10',
    riskLevel: 'high',
    averageSickDays: 15.0,
    frequencyPerYear: 2.0,
    isDauerKrank: false,
    yearlyData: [
      { year: 2022, daysSickness: 10, frequencySick: 3 },
      { year: 2023, daysSickness: 22, frequencySick: 3 },
      { year: 2024, daysSickness: 10, frequencySick: 0 }
    ]
  },
  {
    workerId: 'W0005',
    name: 'Anton Lack',
    gender: 'Male',
    birthYear: 1990,
    jobType: 'IT',
    startDate: '2015-01-08',
    riskLevel: 'low',
    averageSickDays: 10.5,
    frequencyPerYear: 2.6,
    isDauerKrank: false,
    yearlyData: [
      { year: 2022, daysSickness: 15, frequencySick: 3 },
      { year: 2023, daysSickness: 23, frequencySick: 4 },
      { year: 2024, daysSickness: 11, frequencySick: 0 }
    ]
  },
  {
    workerId: 'W0006',
    name: 'Robert Schuler',
    gender: 'Male',
    birthYear: 1992,
    jobType: 'Produktion',
    startDate: '2005-04-21',
    riskLevel: 'high',
    averageSickDays: 13.8,
    frequencyPerYear: 3.0,
    isDauerKrank: false,
    yearlyData: [
      { year: 2022, daysSickness: 18, frequencySick: 3 },
      { year: 2023, daysSickness: 9, frequencySick: 1 },
      { year: 2024, daysSickness: 14, frequencySick: 4 }
    ]
  },
  {
    workerId: 'W0007',
    name: 'Jonathan Gurtel',
    gender: 'Male',
    birthYear: 1988,
    jobType: 'Verwaltung',
    startDate: '2010-03-15',
    riskLevel: 'high',
    averageSickDays: 18.2,
    frequencyPerYear: 3.8,
    isDauerKrank: true,
    yearlyData: [
      { year: 2022, daysSickness: 25, frequencySick: 4 },
      { year: 2023, daysSickness: 22, frequencySick: 5 },
      { year: 2024, daysSickness: 28, frequencySick: 3 }
    ]
  }
];
