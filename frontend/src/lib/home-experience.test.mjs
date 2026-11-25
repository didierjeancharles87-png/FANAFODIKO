import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { medicalSlides, professionalCategories, nextSlideIndex, previousSlideIndex, slideIndexForKey } from "./home-experience.mjs";

test("medical slider contains the five requested themes and valid category actions", () => {
  assert.equal(medicalSlides.length, 5);
  assert.deepEqual(medicalSlides.map(({ visual }) => visual), ["consultation", "pharmacy", "laboratory", "dentist", "specialists"]);
  assert.ok(medicalSlides.every(({ title, description, actionLabel }) => title && description && actionLabel));
  assert.ok(medicalSlides.every(({ image, photographer }) => image && photographer && existsSync(new URL(`../../public${image}`, import.meta.url))));
  assert.ok(medicalSlides.every((slide) => professionalCategories.some((category) => category.code === slide.categoryCode)));
});

test("category selection includes all six Django professional category codes", () => {
  assert.deepEqual(professionalCategories.map(({ code }) => code), [
    "pharmacy", "doctor", "dentist", "laboratory", "delivery_courier", "delivery_company",
  ]);
  assert.ok(professionalCategories.every(({ title, description, detail, icon }) => title && description && detail && icon));
});

test("slider controls wrap around at both ends", () => {
  assert.equal(nextSlideIndex(4, 5), 0);
  assert.equal(previousSlideIndex(0, 5), 4);
  assert.equal(nextSlideIndex(2, 5), 3);
  assert.equal(previousSlideIndex(2, 5), 1);
  assert.equal(nextSlideIndex(0, 0), 0);
});

test("keyboard controls navigate with arrows, Home, and End", () => {
  assert.equal(slideIndexForKey("ArrowRight", 4, 5), 0);
  assert.equal(slideIndexForKey("ArrowLeft", 0, 5), 4);
  assert.equal(slideIndexForKey("Home", 3, 5), 0);
  assert.equal(slideIndexForKey("End", 0, 5), 4);
  assert.equal(slideIndexForKey("Tab", 2, 5), null);
});
