import "./globals.css";
import type { Metadata } from "next";
import React from "react";
import { ServiceWorkerRegistrar } from "../components/sw-registrar";

export const metadata: Metadata = {
  title: "StageCanvas Control",
  description: "Operator dashboard for StageCanvas orchestration",
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="light">
      <head>
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
        <meta name="theme-color" content="#0a0a1a" />
      </head>
      <body>
        <ServiceWorkerRegistrar />
        {children}
      </body>
    </html>
  );
}
