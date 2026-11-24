// Questions per service: one series, so one hue (flag green) and no legend; the title names it.
// Horizontal bars (long Bangla names stay readable at 360 px), <= 24 px thick, 4 px rounded end,
// square at the baseline, a gap between bars, the count just past each bar end in text ink,
// a hover tooltip, and the same numbers in a table for screen readers and printing.

import { Bar, BarChart, CartesianGrid, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useLanguage } from '../../application/languageContext'
import type { ServiceNames } from '../../application/useServiceNames'
import type { ServiceCount } from '../../domain/types'
import { useFormat } from '../format'

const ROW_PX = 36 // 20 px bar + 16 px air
const BAR_PX = 20

export function ServiceBarChart({ data, serviceName }: { data: ServiceCount[]; serviceName: ServiceNames }) {
  const { lang, t } = useLanguage()
  const format = useFormat()
  const rows = data.map((row) => ({ ...row, label: lang === 'bn' ? row.name_bn : serviceName(row.id, lang) }))
  const height = rows.length * ROW_PX + 32

  return (
    <section className="rounded-2xl bg-white p-4 shadow-sm">
      <h2 className="mb-2 text-lg font-bold text-bd-green">{t.byServiceTitle}</h2>
      {/* Axis text and labels use currentColor, so they follow this text colour (no raw colours). */}
      <div className="text-gray-700" style={{ height }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 40, bottom: 4, left: 4 }}>
            <CartesianGrid horizontal={false} stroke="var(--color-bd-green-soft)" />
            <XAxis
              type="number"
              allowDecimals={false}
              tickFormatter={(v: number) => format.number(v)}
              tick={{ fill: 'currentColor', fontSize: 12 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis
              type="category"
              dataKey="label"
              width={lang === 'en' ? 140 : 112}
              tick={{ fill: 'currentColor', fontSize: 14 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              cursor={{ fill: 'var(--color-bd-green-soft)' }}
              formatter={(value) => [format.number(Number(value)), t.questionsWord]}
            />
            <Bar dataKey="count" fill="var(--color-bd-green)" barSize={BAR_PX} radius={[0, 4, 4, 0]} isAnimationActive={false}>
              <LabelList
                dataKey="count"
                position="right"
                formatter={(value: unknown) => format.number(Number(value))}
                style={{ fill: 'currentColor', fontSize: 13 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-bd-green underline">{t.byServiceTable}</summary>
        <table className="mt-2 w-full text-left">
          <thead>
            <tr className="border-b border-gray-200">
              <th className="py-1 font-bold">{t.serviceWord}</th>
              <th className="py-1 text-right font-bold">{t.questionsWord}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-b border-gray-100">
                <td className="py-1">{row.label}</td>
                <td className="py-1 text-right">{format.number(row.count)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  )
}
