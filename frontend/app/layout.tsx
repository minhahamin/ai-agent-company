export const metadata = {
  title: "AI Agent Company",
  description: "Role-based multi-agent collaboration dashboard",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        {children}
      </body>
    </html>
  );
}
