import { redirect } from "next/navigation";

/** Legacy URL — studio widgets live under `/w/...`. */
export default function WidgetsPage() {
  redirect("/w/lx_showcase");
}
