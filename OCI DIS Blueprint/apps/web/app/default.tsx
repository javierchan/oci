/* Root default fallback for the implicit children slot in the App Router shell. */

import { notFound } from "next/navigation";

export default function DefaultRoute(): never {
  notFound();
}
