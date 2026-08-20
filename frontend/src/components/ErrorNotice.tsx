import { Icon } from "./Icon";

export function ErrorNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div className="error-notice" role="alert"><span><Icon name="warning" /> {message}</span>{onRetry && <button className="button button-small button-danger" onClick={onRetry}><Icon name="retry" />重试</button>}</div>;
}
