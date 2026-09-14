import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Дома — наше меню",
  description: "Ваши домашние блюда, совместный выбор и любимые традиции.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Дома", statusBarStyle: "default" },
  icons: {
    icon: "/favicon.svg",
    apple: "/apple-touch-icon.png",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body className="antialiased">{children}</body>
    </html>
  );
}
