import { CHANNEL_PRIORITY, CITES, MAX_PINNED } from "./labels";

/** Channels the explanation cites, in evidence-priority order. */
export function citedChannels(body: string): string[] {
  return CHANNEL_PRIORITY.filter((c) => CITES[c]?.test(body));
}

/** Default pinned channels for a window: cited ones first, padded with wind speed and power. */
export function defaultPins(body: string): string[] {
  const pins = citedChannels(body).slice(0, MAX_PINNED);
  for (const c of ["wind_speed", "power"]) if (pins.length < 2 && !pins.includes(c)) pins.push(c);
  return pins;
}
