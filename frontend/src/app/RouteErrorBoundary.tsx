import { Component, type ErrorInfo, type ReactNode } from "react";
import { ErrorState } from "../components/States";

export class RouteErrorBoundary extends Component<{ children: ReactNode }, { error?: Error }> {
  state: { error?: Error } = {};
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) { window.dispatchEvent(new CustomEvent("emy:frontend-error", { detail: { name: error.name, componentStack: info.componentStack?.slice(0, 500) } })); }
  render() { return this.state.error ? <ErrorState error={this.state.error} retry={() => this.setState({ error: undefined })} /> : this.props.children; }
}
