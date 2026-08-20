import { Link } from "react-router-dom";
import { EmptyState } from "../components/EmptyState";

export function NotFoundPage() {
  return <div className="page"><EmptyState icon="warning" title="这个页面不存在" description="地址可能已变更，返回项目列表继续工作。" action={<Link className="button button-primary" to="/projects">返回项目</Link>} /></div>;
}
