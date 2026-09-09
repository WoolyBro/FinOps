import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

// Stripe's dashboard runs on a tightly-drawn grotesque. Inter is the closest
// open equivalent, and it matters more than any single colour: the default
// Windows fallback is what makes an interface read as unfinished.
const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "FreelanceFlow",
  description: "Billing operations for freelancers, run by an AI agent.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <div className="shell">
          <Sidebar />
          <main className="main">{children}</main>
        </div>
      </body>
    </html>
  );
}
