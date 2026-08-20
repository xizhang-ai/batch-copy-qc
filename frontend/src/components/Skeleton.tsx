export function Skeleton({ lines = 3 }: { lines?: number }) {
  return <div className="form-stack" aria-label="正在加载" aria-busy="true">{Array.from({ length: lines }, (_, index) => <div className="skeleton skeleton-line" style={{ width: `${100 - index * 9}%` }} key={index} />)}</div>;
}
