import type { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = {
  title: "Widgets (redirect)",
};

export default function WidgetsShowcasePage() {
  redirect("/w/lx_showcase");
}
