import type { Metadata } from "next";
import { Geist_Mono } from "next/font/google";
import { Nav } from "@/components/Nav";
import "./globals.css";

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Video RAG · EmbeddingGemma 2",
  description: "Multimodal RAG over Sam Witteveen's videos with EmbeddingGemma 2 and Gemma 4 12B",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col font-sans">
        <Nav />
        <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
