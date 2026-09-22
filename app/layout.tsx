import type { Metadata, Viewport } from "next";
import "./globals.css";
import {TelegramProvider} from "@/components/doma/telegram";
export const viewport:Viewport={width:"device-width",initialScale:1,viewportFit:"cover",interactiveWidget:"resizes-content"};

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
      <body className="antialiased"><TelegramProvider>{children}</TelegramProvider></body>
    </html>
  );
}
