"use client";

import Link from "next/link";
import Image from "next/image";
import { useEffect, useState, type KeyboardEvent } from "react";
import { apiFetch } from "@/lib/api";
import { medicalSlides, nextSlideIndex, previousSlideIndex, professionalCategories, slideIndexForKey, type CategoryCode, type MedicalVisual } from "@/lib/home-experience.mjs";

const SLIDE_INTERVAL_MS = 6500;
const HOME_SLOGANS = [
  "Votre santé, notre priorité.",
  "Des professionnels de santé à votre service.",
] as const;

export function MedicalExperience() {
  const [slideIndex, setSlideIndex] = useState(0);
  const [selectedCategory, setSelectedCategory] = useState<CategoryCode>(professionalCategories[0].code);
  const [isHovered, setIsHovered] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [userPaused, setUserPaused] = useState(false);
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [sloganIndex, setSloganIndex] = useState(0);
  const [isSloganVisible, setIsSloganVisible] = useState(true);
  const [siteImages, setSiteImages] = useState<Record<string, { url: string; alt_text: string }>>({});
  const [hiddenImageSlots, setHiddenImageSlots] = useState<string[]>([]);
  const [homeCopy, setHomeCopy] = useState<{ title: string; introduction: string; body: string } | null>(null);

  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const updatePreference = () => setPrefersReducedMotion(media.matches);
    updatePreference();
    media.addEventListener("change", updatePreference);
    return () => media.removeEventListener("change", updatePreference);
  }, []);

  useEffect(() => {
    void apiFetch<{ images: Array<{ slot: string; url: string; alt_text: string }>; hidden_slots: string[] }>("/v1/site-content/public/images/")
      .then(({ images, hidden_slots }) => {
        setSiteImages(Object.fromEntries(images.map(({ slot, url, alt_text }) => [slot, { url, alt_text }])));
        setHiddenImageSlots(hidden_slots);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let active = true;
    void apiFetch<{ title: string; introduction: string; body: string }>("/v1/site-content/public/pages/home/")
      .then((content) => { if (active) setHomeCopy(content); })
      .catch(() => undefined);
    return () => { active = false; };
  }, []);

  const isPaused = isHovered || isFocused || userPaused || prefersReducedMotion;

  useEffect(() => {
    if (isPaused) return;
    const interval = window.setInterval(() => {
      setSlideIndex((current) => nextSlideIndex(current, medicalSlides.length));
    }, SLIDE_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [isPaused]);

  useEffect(() => {
    if (prefersReducedMotion) {
      setSloganIndex(0);
      setIsSloganVisible(true);
      return;
    }

    let hideTimer: number;
    let showTimer: number;
    const scheduleNextSlogan = () => {
      hideTimer = window.setTimeout(() => {
        setIsSloganVisible(false);
        showTimer = window.setTimeout(() => {
          setSloganIndex((current) => (current + 1) % HOME_SLOGANS.length);
          setIsSloganVisible(true);
          scheduleNextSlogan();
        }, 550);
      }, 5000);
    };

    scheduleNextSlogan();
    return () => {
      window.clearTimeout(hideTimer);
      window.clearTimeout(showTimer);
    };
  }, [prefersReducedMotion]);

  const activeSlide = medicalSlides[slideIndex];
  const imageSlot = ({ teleconsultation: "teleconsultation", pharmacies: "pharmacy", laboratories: "laboratory", dentists: "dentistry", specialists: "specialist" } as const)[activeSlide.id as "teleconsultation" | "pharmacies" | "laboratories" | "dentists" | "specialists"];
  const managedImage = siteImages[imageSlot];
  const imageHidden = hiddenImageSlots.includes(imageSlot);
  const activeCategory = professionalCategories.find(({ code }) => code === selectedCategory) ?? professionalCategories[0];

  function moveSlide(direction: "next" | "previous") {
    setSlideIndex((current) => direction === "next"
      ? nextSlideIndex(current, medicalSlides.length)
      : previousSlideIndex(current, medicalSlides.length));
  }

  function handleSliderKey(event: KeyboardEvent<HTMLElement>) {
    const targetIndex = slideIndexForKey(event.key, slideIndex, medicalSlides.length);
    if (targetIndex === null) return;
    event.preventDefault();
    setSlideIndex(targetIndex);
  }

  function showCategory(code: CategoryCode) {
    setSelectedCategory(code);
    document.getElementById("categories")?.scrollIntoView({ behavior: prefersReducedMotion ? "auto" : "smooth", block: "start" });
  }

  return (
    <>
      <section className="medical-carousel-section" aria-label="À la découverte des services de santé">
        <div className="mx-auto max-w-7xl px-5 pb-7 sm:px-8 sm:pb-9">
          <p className="section-kicker">FANAFODIKO · Santé à Madagascar</p>
          <h1 className="mt-3 max-w-3xl text-3xl font-bold leading-tight tracking-tight text-slate-950 sm:text-4xl lg:text-5xl">{homeCopy?.title ?? <>Un meilleur accès aux soins, <span className="text-gradient">plus proche de vous.</span></>}</h1>
          <p className="mt-4 max-w-2xl whitespace-pre-line text-sm leading-6 text-slate-600 sm:text-base sm:leading-7">{homeCopy?.introduction || "Parcourez les catégories de santé et les services représentés sur la plateforme. Les professionnels consultables seront affichés lorsque l’annuaire public sera ouvert."}</p>
          {homeCopy?.body && <p className="mt-2 max-w-2xl whitespace-pre-line text-sm leading-6 text-slate-600">{homeCopy.body}</p>}
        </div>
        <div className="home-showcase-row">
        <div
          className="medical-carousel"
          role="region"
          aria-roledescription="carrousel"
          aria-label="Présentation de FANAFODIKO"
          tabIndex={0}
          onKeyDown={handleSliderKey}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          onFocusCapture={() => setIsFocused(true)}
          onBlurCapture={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setIsFocused(false);
          }}
        >
          <div className="carousel-slide-layout" aria-live={isPaused ? "polite" : "off"}>
            <div key={activeSlide.id} className="carousel-copy animate-slide-copy">
              <p className="carousel-eyebrow"><span className="carousel-eyebrow-mark" aria-hidden="true" />{activeSlide.eyebrow}</p>
              <h2 className="carousel-title">{activeSlide.title}</h2>
              <p className="carousel-description">{activeSlide.description}</p>
              <button type="button" className="button-primary mt-6" onClick={() => showCategory(activeSlide.categoryCode)}>
                {activeSlide.actionLabel}<span aria-hidden="true">→</span>
              </button>
            </div>
            <div key={`${activeSlide.id}-art`} className={`carousel-art carousel-art-${activeSlide.visual} animate-slide-art`}>
              {!imageHidden && <div className="carousel-art-image">
                <Image src={managedImage?.url ?? activeSlide.image} alt={managedImage?.alt_text || `Photo illustrative : ${activeSlide.eyebrow.toLocaleLowerCase("fr-FR")}.`} fill priority={slideIndex === 0} unoptimized={Boolean(managedImage)} sizes="(max-width: 639px) 90vw, (max-width: 1023px) 45vw, 620px" className="carousel-photo" />
              </div>}
              <aside className="home-slogan-stage" aria-label="Slogans de FANAFODIKO" aria-live="off">
                {HOME_SLOGANS.map((slogan, index) => {
                  const isActiveSlogan = index === sloganIndex && isSloganVisible;
                  return (
                    <p
                      key={slogan}
                      className={`home-slogan-panel ${isActiveSlogan ? "home-slogan-panel-active" : "home-slogan-panel-hidden"}`}
                      aria-hidden={!isActiveSlogan}
                    >
                      {slogan}
                    </p>
                  );
                })}
              </aside>
              {!imageHidden && <span className="art-caption">{managedImage ? "Image fournie par FANAFODIKO" : `Photo illustrative · Pexels · ${activeSlide.photographer}`}</span>}
            </div>
          </div>

          <div className="carousel-controls">
            <div className="carousel-controls-left">
              <button type="button" className="carousel-arrow" aria-label="Diapositive précédente" onClick={() => moveSlide("previous")}><ArrowIcon direction="left" /></button>
              <button type="button" className="carousel-arrow" aria-label="Diapositive suivante" onClick={() => moveSlide("next")}><ArrowIcon direction="right" /></button>
              <span className="carousel-count"><span>{String(slideIndex + 1).padStart(2, "0")}</span> / {String(medicalSlides.length).padStart(2, "0")}</span>
            </div>
            <div className="carousel-dots" aria-label="Choisir une diapositive">
              {medicalSlides.map((slide, index) => (
                <button
                  key={slide.id}
                  type="button"
                  className={`carousel-dot ${index === slideIndex ? "carousel-dot-active" : ""}`}
                  aria-label={`Afficher ${slide.eyebrow.toLocaleLowerCase("fr-FR")}`}
                  aria-current={index === slideIndex ? "step" : undefined}
                  onClick={() => setSlideIndex(index)}
                />
              ))}
            </div>
            {!prefersReducedMotion && (
              <button type="button" className="carousel-pause" onClick={() => setUserPaused((paused) => !paused)}>
                {userPaused ? <PlayIcon /> : <PauseIcon />}
                <span className="sr-only">{userPaused ? "Reprendre le défilement automatique" : "Mettre en pause le défilement automatique"}</span>
              </button>
            )}
            {prefersReducedMotion && <span className="sr-only">Défilement automatique désactivé selon vos préférences de mouvement.</span>}
          </div>
        </div>
        </div>
      </section>

      <section id="categories" className="section-wrap scroll-mt-24 bg-white py-16 sm:py-20">
        <div className="mx-auto max-w-7xl px-5 sm:px-8">
          <div className="section-heading">
            <div><p className="section-kicker">Un espace pour chaque besoin</p><h2 className="section-title">Les services de santé, réunis simplement.</h2></div>
            <p className="section-intro">Choisissez une catégorie pour en savoir plus. L’annuaire public n’est pas encore disponible.</p>
          </div>
          <div className="mt-9 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {professionalCategories.map((category) => (
              <article key={category.code} className={`category-preview ${category.code === selectedCategory ? "category-preview-selected" : ""}`}>
                <span className={`category-symbol category-symbol-${category.icon}`} aria-hidden="true"><CategoryIcon icon={category.icon} /></span>
                <div className="min-w-0"><h3 className="font-semibold text-slate-900">{category.title}</h3><p className="mt-1 text-sm leading-5 text-slate-500">{category.description}</p></div>
                <button
                  type="button"
                  className="category-select-button"
                  aria-pressed={category.code === selectedCategory}
                  aria-controls="category-details"
                  onClick={() => setSelectedCategory(category.code)}
                >Découvrir</button>
              </article>
            ))}
          </div>

          <article id="category-details" className="category-details-panel" aria-live="polite" aria-atomic="true">
            <div className="category-details-copy">
              <span className={`category-symbol category-symbol-${activeCategory.icon}`} aria-hidden="true"><CategoryIcon icon={activeCategory.icon} /></span>
              <div><p className="section-kicker">{activeCategory.title}</p><h3 className="mt-1 text-xl font-bold tracking-tight text-slate-900">{activeCategory.description}</h3><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600">{activeCategory.detail}</p></div>
            </div>
            <div className="category-empty-state">
              <span className="category-empty-icon" aria-hidden="true"><DirectoryIcon /></span>
              <div><h4>Aucun professionnel publié pour le moment</h4><p>Les profils apparaîtront ici lorsque l’annuaire public sera ouvert et que des données pourront être publiées.</p></div>
            </div>
            <div className="category-details-footer">
              <span className="category-status"><span /> Annuaire en préparation</span>
              <Link href="/professionnel/inscription" className="text-link">Vous êtes professionnel ? Rejoindre FANAFODIKO <span aria-hidden="true">→</span></Link>
            </div>
          </article>
        </div>
      </section>
    </>
  );
}

function CategoryIcon({ icon }: { icon: "pharmacy" | "doctor" | "dentist" | "laboratory" | "courier" | "company" | MedicalVisual }) {
  const common = { viewBox: "0 0 32 32", className: "h-6 w-6", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (icon) {
    case "pharmacy": return <svg {...common}><path d="M7 12.5h18v13H7zM10 12.5V9a6 6 0 0 1 12 0v3.5"/><path d="M16 16v6m-3-3h6"/></svg>;
    case "doctor":
    case "consultation":
    case "specialists": return <svg {...common}><circle cx="16" cy="9" r="4.5"/><path d="M6.5 26a9.5 9.5 0 0 1 19 0M16 17v6m-3-3h6"/></svg>;
    case "dentist": return <svg {...common}><path d="M11 5.5c2.1 0 3 1 5 1s2.9-1 5-1c3 0 5 2.3 5 5.7 0 5.1-3.6 15.3-6.5 15.3-2.2 0-1.4-7.5-3.5-7.5s-1.3 7.5-3.5 7.5C9.6 26.5 6 16.3 6 11.2c0-3.4 2-5.7 5-5.7Z"/></svg>;
    case "laboratory": return <svg {...common}><path d="M12 5h8m-6 0v8l-6.5 10.2A2.5 2.5 0 0 0 9.6 27h12.8a2.5 2.5 0 0 0 2.1-3.8L18 13V5"/><path d="M11.5 20h9m-7-4h5"/></svg>;
    case "courier": return <svg {...common}><path d="M5 10h14v13H5zM19 14h4l4 4v5h-8z"/><circle cx="10" cy="24" r="2.5"/><circle cx="23" cy="24" r="2.5"/><path d="M9 14h6"/></svg>;
    case "company": return <svg {...common}><path d="M5 27h22M8 27V8h11v19m0-11h6v11M11 12h2m3 0h1m-6 4h2m3 0h1m-5 4h2m3 0h1"/><path d="M11 8V5h6v3"/></svg>;
  }
}

function DirectoryIcon() {
  return <svg aria-hidden="true" viewBox="0 0 32 32" className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M7 7.5h18v18H7zM11 12h10m-10 4h10m-10 4h6"/><path d="M11 4.5v6m10-6v6"/></svg>;
}

function ArrowIcon({ direction }: { direction: "left" | "right" }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={direction === "left" ? "M19 12H5m7 7-7-7 7-7" : "M5 12h14m-7-7 7 7-7 7"}/></svg>;
}

function PauseIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor"><path d="M7 5h4v14H7zm6 0h4v14h-4z"/></svg>;
}

function PlayIcon() {
  return <svg aria-hidden="true" viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor"><path d="M8 5.8v12.4a1 1 0 0 0 1.5.86l10-6.2a1 1 0 0 0 0-1.72l-10-6.2A1 1 0 0 0 8 5.8Z"/></svg>;
}
