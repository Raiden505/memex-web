import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Memex",
    short_name: "Memex",
    description: "Your extended cognitive field.",
    start_url: "/chat",
    display: "standalone",
    background_color: "#f8f9fa",
    theme_color: "#00236f",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        purpose: "any maskable" as any,
      },
    ],
  };
}
