import type { Metadata } from "next";
import { Providers } from "./providers";
import { Nav } from "./components/Nav";

export const metadata: Metadata = {
  title: "django-dynamic-user playground — default host",
  description: "Phase 8 playground — docs/APP-DESIGN.md §11.2",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: "2rem", maxWidth: "48rem" }}>
        <Providers>
          <Nav />
          {children}
        </Providers>
      </body>
    </html>
  );
}
