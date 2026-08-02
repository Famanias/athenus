import "./globals.css";

export const metadata = {
  title: "Athenus Knowledge OS",
  description: "AI-Native Learning Platform & Knowledge Operating System",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
