import Papa from 'papaparse';

interface RiskMap {
  [workerId: string]: boolean;
}


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
export function loadWorkerDataFromCsv(
  workerCsvText: string,
  riskCsvText: string
): WorkerData[] {
  const workerResults = Papa.parse(workerCsvText, {
    header: true,
    skipEmptyLines: true
  });

  const riskResults = Papa.parse(riskCsvText, {
    header: true,
    skipEmptyLines: true
  });

  const riskMap: RiskMap = {};
  riskResults.data.forEach((row: any) => {
    riskMap[row.Worker_ID] = row.risk == '1';
  });

  const grouped = new Map<string, any[]>();
  workerResults.data.forEach((row: any) => {
    if (!grouped.has(row.Worker_ID)) {
      grouped.set(row.Worker_ID, []);
    }
    grouped.get(row.Worker_ID)!.push(row);
  });

  const workers: WorkerData[] = [];

  grouped.forEach((entries, workerId) => {
    const base = entries[0];
    const yearlyData: YearlyData[] = entries.map((entry) => ({
      year: Number(entry.Year),
      daysSickness: Number(entry.Days_Sickness_Per_Year),
      frequencySick: Number(entry.Frequency_Sick_Days)
    }));

    const averageSickDays =
      yearlyData.reduce((sum, y) => sum + y.daysSickness, 0) / yearlyData.length;

    const frequencyPerYear =
      yearlyData.reduce((sum, y) => sum + y.frequencySick, 0) / yearlyData.length;

    const worker: WorkerData = {
      workerId,
      name: `BENUTZER ${workerId.slice(-2)}`,
      gender: base.Gender,
      birthYear: Number(base.Birth_Year),
      jobType: base.Job_Type,
      startDate: base.Start_Date_Employment,
      riskLevel: riskMap[workerId] ? 'high' : 'low',
      averageSickDays: parseFloat(averageSickDays.toFixed(1)),
      frequencyPerYear: parseFloat(frequencyPerYear.toFixed(1)),
      isDauerKrank: averageSickDays > 20, // example logic
      yearlyData
    };

    workers.push(worker);
  });

  return workers;
}


const workerCsv = await fetch('absence_dataset.csv').then(res => res.text());
const riskCsv = await fetch('prediction.csv').then(res => res.text());

export const mockWorkers = loadWorkerDataFromCsv(workerCsv, riskCsv);
console.log(mockWorkers);

