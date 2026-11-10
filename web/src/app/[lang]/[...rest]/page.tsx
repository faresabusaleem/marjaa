import { notFound } from "next/navigation";

// Any unknown path renders [lang]/not-found.tsx inside the site layout.
export default function CatchAll() {
  notFound();
}
