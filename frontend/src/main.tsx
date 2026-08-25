import React from "react";
import ReactDOM from "react-dom/client";
import { HashRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import { FeatureProvider } from "./app/FeatureContext";
import { PreferencesProvider } from "./app/PreferencesContext";
import "./styles.css";

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 10_000 }, mutations: { retry: false } } });
ReactDOM.createRoot(document.getElementById("root")!).render(<React.StrictMode><QueryClientProvider client={queryClient}><PreferencesProvider><FeatureProvider><HashRouter><App /></HashRouter></FeatureProvider></PreferencesProvider></QueryClientProvider></React.StrictMode>);
