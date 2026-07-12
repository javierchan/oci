/* Shared browser event contract for opening the workspace command palette. */

export const OPEN_COMMAND_PALETTE_EVENT = "oci-dis:open-command-palette";

export function requestOpenCommandPalette(): void {
  window.dispatchEvent(new Event(OPEN_COMMAND_PALETTE_EVENT));
}
