// The service an answer is about, as a small green tag (SRS 3.3).

export function ServiceTag({ name }: { name: string }) {
  return (
    <span className="inline-block rounded-full bg-bd-green-soft px-3 py-1 text-sm font-bold text-bd-green">
      {name}
    </span>
  )
}
