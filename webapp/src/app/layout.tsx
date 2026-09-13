import type { Metadata } from "next";
import { Barlow, Barlow_Semi_Condensed, JetBrains_Mono, Source_Serif_4 } from "next/font/google";

import Footer from "@/components/Footer";
import TopBar from "@/components/TopBar";
import { loadDemo } from "@/lib/data";

import "./globals.css";

const ui = Barlow({ weight: ["400", "500", "600", "700"], subsets: ["latin"], variable: "--font-ui", display: "swap" });
const condensed = Barlow_Semi_Condensed({ weight: ["500", "600"], subsets: ["latin"], variable: "--font-condensed", display: "swap" });
const serif = Source_Serif_4({ weight: ["400", "600"], subsets: ["latin"], variable: "--font-serif", display: "swap" });
const mono = JetBrains_Mono({ weight: ["400", "500"], subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: { default: "Turbine Alarm Explainer", template: "%s · Turbine Alarm Explainer" },
  description: "Early warning from 24 h of wind-turbine SCADA, with checkable evidence — held-out demo windows and every model's results.",
};

// Applies a saved theme before first paint so the page never flashes the other theme.
const themeScript = `(function(){try{var t=localStorage.getItem("tae-theme");if(t==="dark"||t==="light")document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const { meta, windows } = loadDemo();
  return (
    <html lang="en" suppressHydrationWarning className={`${ui.variable} ${condensed.variable} ${serif.variable} ${mono.variable}`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <div className="wrap">
          <TopBar />
          {children}
          <Footer nWindows={windows.length} model={meta.model} />
        </div>
      </body>
    </html>
  );
}
