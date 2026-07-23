"use client";

import { Check, ChevronDown } from "lucide-react";
import {
  type CSSProperties,
  createRef,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

export type GovernedSelectOption = {
  value: string;
  label: string;
  description?: string;
  group?: string;
  disabled?: boolean;
};

type GovernedSelectProps = {
  ariaLabel: string;
  value: string;
  options: GovernedSelectOption[];
  onChange: (_value: string) => void;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  size?: "default" | "compact";
};

type MenuPosition = CSSProperties & {
  maxHeight: number;
};

const MENU_GAP = 6;
const MENU_MAX_HEIGHT = 304;
const VIEWPORT_MARGIN = 12;

export function GovernedSelect({
  ariaLabel,
  value,
  options,
  onChange,
  placeholder = "Choose an option",
  disabled = false,
  className = "",
  size = "default",
}: GovernedSelectProps): JSX.Element {
  const listId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const optionRefs = useMemo(
    () => options.map(() => createRef<HTMLButtonElement>()),
    [options],
  );
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [menuPosition, setMenuPosition] = useState<MenuPosition | null>(null);

  const selectedIndex = options.findIndex((option) => option.value === value);
  const selectedOption = selectedIndex >= 0 ? options[selectedIndex] : undefined;
  const enabledIndexes = options
    .map((option, index) => (option.disabled ? -1 : index))
    .filter((index) => index >= 0);

  function positionMenu(): void {
    const trigger = triggerRef.current;
    if (!trigger) return;
    const rect = trigger.getBoundingClientRect();
    const width = Math.min(
      Math.max(rect.width, 220),
      Math.max(window.innerWidth - (VIEWPORT_MARGIN * 2), 220),
    );
    const left = Math.min(
      Math.max(rect.left, VIEWPORT_MARGIN),
      Math.max(window.innerWidth - width - VIEWPORT_MARGIN, VIEWPORT_MARGIN),
    );
    const availableBelow = window.innerHeight - rect.bottom - VIEWPORT_MARGIN - MENU_GAP;
    const availableAbove = rect.top - VIEWPORT_MARGIN - MENU_GAP;
    const openAbove = availableBelow < 220 && availableAbove > availableBelow;
    const maxHeight = Math.max(
      120,
      Math.min(MENU_MAX_HEIGHT, openAbove ? availableAbove : availableBelow),
    );

    setMenuPosition(
      openAbove
        ? {
            bottom: window.innerHeight - rect.top + MENU_GAP,
            left,
            width,
            maxHeight,
          }
        : {
            left,
            top: rect.bottom + MENU_GAP,
            width,
            maxHeight,
          },
    );
  }

  function openMenu(): void {
    if (disabled || enabledIndexes.length === 0) return;
    const nextIndex = selectedIndex >= 0 && !options[selectedIndex]?.disabled
      ? selectedIndex
      : enabledIndexes[0];
    setActiveIndex(nextIndex);
    setOpen(true);
  }

  function closeMenu({ restoreFocus = false }: { restoreFocus?: boolean } = {}): void {
    setOpen(false);
    setMenuPosition(null);
    if (restoreFocus) {
      window.requestAnimationFrame(() => triggerRef.current?.focus());
    }
  }

  function selectOption(index: number): void {
    const option = options[index];
    if (!option || option.disabled) return;
    onChange(option.value);
    closeMenu({ restoreFocus: true });
  }

  function moveActive(direction: 1 | -1): void {
    if (enabledIndexes.length === 0) return;
    const currentPosition = enabledIndexes.indexOf(activeIndex);
    const nextPosition = currentPosition < 0
      ? 0
      : (currentPosition + direction + enabledIndexes.length) % enabledIndexes.length;
    setActiveIndex(enabledIndexes[nextPosition]);
  }

  useEffect(() => {
    if (!open) return undefined;

    positionMenu();
    function handlePointerDown(event: PointerEvent): void {
      const target = event.target as Node;
      if (!triggerRef.current?.contains(target) && !menuRef.current?.contains(target)) {
        closeMenu();
      }
    }
    function handleViewportChange(): void {
      positionMenu();
    }

    document.addEventListener("pointerdown", handlePointerDown);
    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);
    return () => {
      document.removeEventListener("pointerdown", handlePointerDown);
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    optionRefs[activeIndex]?.current?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, open, optionRefs]);

  let previousGroup: string | undefined;

  return (
    <div className={`min-w-0 ${className}`}>
      <button
        ref={triggerRef}
        type="button"
        role="combobox"
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-controls={listId}
        aria-expanded={open}
        aria-activedescendant={open ? `${listId}-option-${activeIndex}` : undefined}
        disabled={disabled}
        onClick={() => (open ? closeMenu() : openMenu())}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown") {
            event.preventDefault();
            if (!open) openMenu();
            else moveActive(1);
          } else if (event.key === "ArrowUp") {
            event.preventDefault();
            if (!open) openMenu();
            else moveActive(-1);
          } else if (event.key === "Home" && open) {
            event.preventDefault();
            setActiveIndex(enabledIndexes[0]);
          } else if (event.key === "End" && open) {
            event.preventDefault();
            setActiveIndex(enabledIndexes[enabledIndexes.length - 1]);
          } else if ((event.key === "Enter" || event.key === " ") && open) {
            event.preventDefault();
            selectOption(activeIndex);
          } else if (event.key === "Escape" && open) {
            event.preventDefault();
            closeMenu({ restoreFocus: true });
          }
        }}
        className={`group flex w-full items-center justify-between gap-3 rounded-lg border bg-[var(--color-surface)] px-3 text-left text-[var(--color-text-primary)] shadow-sm transition ${
          size === "compact" ? "h-9 text-sm" : "min-h-10 py-2.5 text-sm"
        } ${
          open
            ? "border-[var(--color-accent)] ring-2 ring-[var(--color-accent-soft)]"
            : "border-[var(--color-border)] hover:border-[var(--color-line-strong)] hover:bg-[var(--color-surface-2)]"
        } disabled:cursor-not-allowed disabled:opacity-55 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-accent-soft)]`}
      >
        <span className={`min-w-0 flex-1 truncate ${selectedOption ? "font-medium" : "text-[var(--color-text-muted)]"}`}>
          {selectedOption?.label ?? placeholder}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={`h-4 w-4 shrink-0 text-[var(--color-text-muted)] transition-transform ${open ? "rotate-180" : ""}`}
        />
      </button>

      {open && menuPosition && typeof document !== "undefined"
        ? createPortal(
            <div
              ref={menuRef}
              id={listId}
              role="listbox"
              aria-label={`${ariaLabel} options`}
              style={menuPosition}
              className="fixed z-[120] overflow-y-auto rounded-lg border border-[var(--color-border)] bg-[var(--color-surface)] p-1.5 shadow-[0_18px_48px_rgba(0,0,0,0.2)]"
              onKeyDown={(event) => {
                if (event.key === "Escape") {
                  event.preventDefault();
                  closeMenu({ restoreFocus: true });
                }
              }}
            >
              {options.map((option, index) => {
                const showGroup = option.group && option.group !== previousGroup;
                previousGroup = option.group;
                return (
                  <div key={`${option.group ?? "option"}-${option.value}`}>
                    {showGroup ? (
                      <p className="sticky top-0 z-10 bg-[var(--color-surface)] px-3 pb-1.5 pt-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-[var(--color-text-muted)]">
                        {option.group}
                      </p>
                    ) : null}
                    <button
                      ref={optionRefs[index]}
                      id={`${listId}-option-${index}`}
                      type="button"
                      role="option"
                      aria-selected={option.value === value}
                      disabled={option.disabled}
                      onMouseEnter={() => {
                        if (!option.disabled) setActiveIndex(index);
                      }}
                      onClick={() => selectOption(index)}
                      className={`flex w-full items-start gap-3 rounded-md px-3 py-2.5 text-left transition ${
                        index === activeIndex
                          ? "bg-[var(--color-hover)] text-[var(--color-text-primary)]"
                          : "text-[var(--color-text-secondary)]"
                      } disabled:cursor-not-allowed disabled:opacity-45`}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block text-sm font-medium leading-5">{option.label}</span>
                        {option.description ? (
                          <span className="mt-0.5 block text-xs leading-4 text-[var(--color-text-muted)]">
                            {option.description}
                          </span>
                        ) : null}
                      </span>
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center">
                        {option.value === value ? (
                          <Check className="h-4 w-4 text-[var(--color-accent)]" aria-hidden="true" />
                        ) : null}
                      </span>
                    </button>
                  </div>
                );
              })}
            </div>,
            document.body,
          )
        : null}
    </div>
  );
}
