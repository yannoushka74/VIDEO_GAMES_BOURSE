import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getAutocomplete, type AutocompleteSuggestion } from "../api";

interface Props {
  value: string;
  onChange: (value: string) => void;
}

function SearchAutocomplete({ value, onChange }: Props) {
  const [suggestions, setSuggestions] = useState<AutocompleteSuggestion[]>([]);
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const navigate = useNavigate();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>();

  // Debounced fetch
  useEffect(() => {
    if (value.length < 2) {
      setSuggestions([]);
      setOpen(false);
      return;
    }

    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      getAutocomplete(value).then((data) => {
        setSuggestions(data);
        setOpen(data.length > 0);
        setActiveIndex(-1);
      });
    }, 250);

    return () => clearTimeout(timerRef.current);
  }, [value]);

  // Fermer au clic extérieur
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const selectSuggestion = (s: AutocompleteSuggestion) => {
    setOpen(false);
    onChange(s.title);
    navigate(`/games/${s.id}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!open) return;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      selectSuggestion(suggestions[activeIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div className="autocomplete" ref={wrapperRef}>
      <input
        type="text"
        placeholder="Rechercher un jeu..."
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => suggestions.length > 0 && setOpen(true)}
        onKeyDown={handleKeyDown}
      />
      {open && (
        <ul className="autocomplete__list">
          {suggestions.map((s, i) => (
            <li
              key={s.id}
              className={`autocomplete__item ${i === activeIndex ? "autocomplete__item--active" : ""}`}
              onMouseEnter={() => setActiveIndex(i)}
              onMouseDown={() => selectSuggestion(s)}
            >
              {s.cover_url ? (
                <img className="autocomplete__cover" src={s.cover_url} alt="" />
              ) : (
                <div className="autocomplete__cover autocomplete__cover--empty" />
              )}
              <span className="autocomplete__title">{s.title}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default SearchAutocomplete;
