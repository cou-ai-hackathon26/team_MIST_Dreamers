// One KPI on the admin dashboard: a big number with its label (SRS 3.4).

export function StatCard({ label, value, unit }: { label: string; value: string; unit?: string }) {
  return (
    <div className="rounded-2xl bg-white p-4 shadow-sm">
      <p className="text-sm font-bold text-gray-600">{label}</p>
      <p className="mt-1 text-3xl font-bold text-bd-green">
        {value}
        {unit && <span className="ml-1 text-base font-normal text-gray-600">{unit}</span>}
      </p>
    </div>
  )
}
