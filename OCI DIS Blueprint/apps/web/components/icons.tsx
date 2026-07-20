"use client";

/* Consistent 16x16 inline SVG icons for the redesign shell and topology surfaces. */

import type { ReactNode, SVGProps } from "react";
import Image from "next/image";

type IconProps = SVGProps<SVGSVGElement> & {
  size?: number;
  children?: ReactNode;
};

export function Icon({ size = 16, children, ...props }: IconProps): JSX.Element {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export function OciMark({
  size = 24,
  className,
}: {
  size?: number;
  className?: string;
}): JSX.Element {
  return (
    <Image
      src="/oracle-brandmark.svg"
      width={size}
      height={size}
      className={className}
      alt=""
      aria-hidden="true"
    />
  );
}

export function SearchIcon(props: IconProps): JSX.Element {
  return (
    <Icon {...props}>
      <path d="M7 12.5a5.5 5.5 0 1 0 0-11 5.5 5.5 0 0 0 0 11ZM14 14l-3-3" />
    </Icon>
  );
}

export function HomeIcon(props: IconProps): JSX.Element {
  return (
    <Icon {...props}>
      <path d="M2.5 7.5L8 3l5.5 4.5V13a1 1 0 0 1-1 1H3.5a1 1 0 0 1-1-1V7.5Z" />
    </Icon>
  );
}

export function CatalogIcon(props: IconProps): JSX.Element {
  return (
    <Icon {...props}>
      <path d="M2.5 4h11M2.5 8h11M2.5 12h11" />
      <circle cx="2.5" cy="4" r="0.6" fill="currentColor" stroke="none" />
      <circle cx="2.5" cy="8" r="0.6" fill="currentColor" stroke="none" />
      <circle cx="2.5" cy="12" r="0.6" fill="currentColor" stroke="none" />
    </Icon>
  );
}

export function GraphIcon(props: IconProps): JSX.Element {
  return (
    <Icon {...props}>
      <circle cx="3.5" cy="4" r="1.5" />
      <circle cx="12.5" cy="4" r="1.5" />
      <circle cx="8" cy="12" r="1.5" />
      <path d="M4.5 5l3 6M11.5 5l-3 6" />
    </Icon>
  );
}

export function UploadIcon(props: IconProps): JSX.Element {
  return (
    <Icon {...props}>
      <path d="M8 10V3M5 6l3-3 3 3M3 11v1a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1v-1" />
    </Icon>
  );
}

export function CaptureIcon(props: IconProps): JSX.Element {
  return (
    <Icon {...props}>
      <path d="M3 10.5L6 7l2 2 4.5-5M9 4.5h4v4" />
    </Icon>
  );
}

export function AdminIcon(props: IconProps): JSX.Element {
  return (
    <Icon {...props}>
      <circle cx="8" cy="8" r="1.5" />
      <path d="M8 1.5v2M8 12.5v2M14.5 8h-2M3.5 8h-2M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4M12.6 12.6l-1.4-1.4M4.8 4.8L3.4 3.4" />
    </Icon>
  );
}

export function DatabaseIcon(props: IconProps): JSX.Element {
  return (
    <Icon {...props}>
      <ellipse cx="8" cy="3.5" rx="5" ry="1.5" />
      <path d="M3 3.5v5c0 .8 2.2 1.5 5 1.5s5-.7 5-1.5v-5M3 8.5v4c0 .8 2.2 1.5 5 1.5s5-.7 5-1.5v-4" />
    </Icon>
  );
}

export function ShieldIcon(props: IconProps): JSX.Element {
  return (
    <Icon {...props}>
      <path d="M8 1.5L2.5 4v4c0 3.3 2.5 6 5.5 6.5C11 13.5 13.5 10.8 13.5 7.5V4L8 1.5Z" />
    </Icon>
  );
}

export function FolderIcon(props: IconProps): JSX.Element {
  return (
    <Icon {...props}>
      <path d="M2 4.5a1 1 0 0 1 1-1h3l1.5 1.5H13a1 1 0 0 1 1 1V12a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1V4.5Z" />
    </Icon>
  );
}

export function ChevronRightIcon(props: IconProps): JSX.Element {
  return (
    <Icon {...props}>
      <path d="M6 3l5 5-5 5" />
    </Icon>
  );
}
