<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { previewInquiry } from "./preview-inquiry.ts";
import { inquiryErrorMessage, SubmitInquiryError, submitInquiry } from "./submit-inquiry.ts";
import { notifyInquiryChanged } from "../lib/inquiry-events.ts";
import {
  hasUnavailableItem,
  loadInquiryItems,
  previewedPricePresentation,
  previewRequest,
  removeInquiryItem,
  saveInquiryItems,
  selectionInquiry,
  specificationLine,
} from "../lib/inquiry-state.ts";
import type { InquiryItem, PreviewedItem } from "../lib/inquiry-state.ts";
import type { PricePresentation } from "../lib/calculator-state.ts";

interface Row {
  key: string;
  index: number;
  name: string;
  size: string;
  lines: string[];
  price: PricePresentation | null;
  wish: string;
  isGone: boolean;
  isWish: boolean;
  editable: boolean;
}

const items = ref<InquiryItem[]>([]);
const preview = ref<PreviewedItem[] | null>(null);
const previewFailed = ref(false);
const sent = ref<PreviewedItem[] | null>(null);
const isLoaded = ref(false);
const name = ref("");
const phone = ref("");
const email = ref("");
const comment = ref("");
const consent = ref(false);
const isSubmitting = ref(false);
const result = ref<{ text: string; isError: boolean } | null>(null);
// A preview answering after a position was removed would be paired with the
// wrong rows: only the latest request is allowed to land.
let previewGeneration = 0;

const isEmpty = computed(() => isLoaded.value && sent.value === null && items.value.length === 0);
const hasGone = computed(() => preview.value !== null && hasUnavailableItem(preview.value));
const canSend = computed(() => !isSubmitting.value && items.value.length > 0 && !hasGone.value);

// One markup for both readings of a position: the page before sending draws the
// stored position with what the preview said about it, the summary after
// sending draws what the server stored — the same projection (rule 20).
const rows = computed<Row[]>(() => {
  if (sent.value !== null) {
    return sent.value.map((previewed, index) => previewedRow(previewed, index, null));
  }
  return items.value.map((item, index) => {
    const previewed = preview.value?.[index] ?? null;
    return previewed === null ? storedRow(item, index) : previewedRow(previewed, index, item);
  });
});

function storedRow(item: InquiryItem, index: number): Row {
  return {
    key: `${item.productId}-${index}`,
    index,
    name: item.productName,
    size: `${item.widthMm} × ${item.heightMm} мм`,
    lines: [],
    price: null,
    wish: item.wish,
    isGone: false,
    isWish: item.isWish,
    editable: true,
  };
}

function previewedRow(previewed: PreviewedItem, index: number, item: InquiryItem | null): Row {
  const configuration = previewed.configuration;
  return {
    key: `${previewed.product_id}-${index}`,
    index,
    name: previewed.product_name ?? item?.productName ?? "Товар",
    size: configuration === null
      ? (item === null ? "" : `${item.widthMm} × ${item.heightMm} мм`)
      : `${configuration.width_mm} × ${configuration.height_mm} мм`,
    lines: configuration?.values.map(specificationLine) ?? [],
    price: previewedPricePresentation(previewed),
    wish: item?.wish ?? previewed.wish,
    isGone: !previewed.is_available,
    isWish: false,
    editable: item !== null,
  };
}

function priceText(price: PricePresentation): string {
  return price.kind === "priced" ? `${Number(price.total).toLocaleString("ru-RU")} ₽` : (price.message ?? "");
}

async function loadPreview(): Promise<void> {
  const generation = ++previewGeneration;
  previewFailed.value = false;
  if (items.value.length === 0) {
    preview.value = [];
    return;
  }
  try {
    const answered = (await previewInquiry(previewRequest(items.value))).items;
    if (generation === previewGeneration) {
      preview.value = answered;
    }
  } catch {
    if (generation === previewGeneration) {
      previewFailed.value = true;
    }
  }
}

function removeItem(index: number): void {
  items.value = removeInquiryItem(window.localStorage, items.value, index);
  notifyInquiryChanged(window);
  if (preview.value === null) {
    // Nothing has landed yet: the request in flight would answer for the old
    // rows, so it is dropped and a fresh one asks for the rows that remain.
    void loadPreview();
    return;
  }
  preview.value = preview.value.filter((_, itemIndex) => itemIndex !== index);
  previewGeneration += 1;
}

function updateWish(index: number, event: Event): void {
  const item = items.value[index];
  if (item === undefined || !(event.target instanceof HTMLTextAreaElement)) {
    return;
  }
  item.wish = event.target.value;
  saveInquiryItems(window.localStorage, items.value);
}

async function send(): Promise<void> {
  if (!canSend.value) {
    return;
  }
  isSubmitting.value = true;
  result.value = null;
  try {
    const accepted = await submitInquiry(selectionInquiry(items.value, {
      name: name.value,
      phone: phone.value,
      email: email.value,
      consent: consent.value,
    }, comment.value));
    sent.value = accepted.items;
    items.value = [];
    preview.value = null;
    saveInquiryItems(window.localStorage, items.value);
    notifyInquiryChanged(window);
    comment.value = "";
    result.value = { text: "Спасибо! Заявка отправлена, менеджер свяжется с вами.", isError: false };
  } catch (error) {
    result.value = {
      text: error instanceof SubmitInquiryError ? inquiryErrorMessage(error) : "Не удалось отправить заявку. Попробуйте ещё раз.",
      isError: true,
    };
  } finally {
    isSubmitting.value = false;
  }
}

onMounted(async () => {
  items.value = loadInquiryItems(window.localStorage);
  isLoaded.value = true;
  await loadPreview();
});
</script>

<template>
  <div class="inquiry">
    <div>
      <ul v-if="rows.length > 0" class="inquiry-items">
        <li v-for="row in rows" :key="row.key" :class="{ 'inquiry-item--gone': row.isGone }">
          <span>
            <b>{{ row.name }}</b>
            <small v-if="row.size">{{ row.size }}<span v-if="row.isWish"> · индивидуальное пожелание</span></small>
            <ul v-if="row.lines.length > 0" class="inquiry-spec"><li v-for="line in row.lines" :key="line">{{ line }}</li></ul>
            <span v-if="row.isGone" class="inquiry-price inquiry-price--words inquiry-price--gone">Товар снят с продажи — уберите его из заявки.</span>
            <strong v-else-if="row.price?.kind === 'priced'" class="inquiry-price">{{ priceText(row.price) }}</strong>
            <span v-else-if="row.price" class="inquiry-price inquiry-price--words">{{ priceText(row.price) }}</span>
            <label v-if="row.editable && !row.isGone" class="field inquiry-wish"><span>Пожелание</span><textarea :value="row.wish" rows="2" maxlength="1000" placeholder="Что важно учесть" @input="updateWish(row.index, $event)" /></label>
            <span v-else-if="row.wish" class="muted">{{ row.wish }}</span>
          </span>
          <button v-if="row.editable" class="inquiry-remove" type="button" @click="removeItem(row.index)">{{ row.isGone ? "Убрать" : "Удалить" }}</button>
        </li>
      </ul>
      <p v-if="previewFailed" class="inquiry-note error" aria-live="polite">Не удалось показать цены и характеристики. <button class="inquiry-retry" type="button" @click="loadPreview">Повторить</button></p>
      <div v-if="isEmpty" class="empty">
        <p class="sub">Пока пусто.</p>
        <a class="btn btn--ghost btn--sm" href="/catalog/">Перейти в каталог <span class="arrow" aria-hidden="true">→</span></a>
      </div>
    </div>
    <aside class="inquiry-panel">
      <template v-if="sent !== null">
        <h2>Заявка отправлена</h2>
        <p class="muted">Спасибо! Менеджер свяжется с вами. Слева — то, что ушло ему вместе с вашими контактами.</p>
        <a class="btn btn--ghost btn--sm" href="/catalog/">Вернуться в каталог <span class="arrow" aria-hidden="true">→</span></a>
      </template>
      <template v-else>
        <h2>Оставить заявку</h2>
        <p class="muted">Отправим подборку менеджеру вместе с вашими контактами.</p>
        <form class="inquiry-form" @submit.prevent="send">
          <label class="field"><span>Ваше имя *</span><input v-model="name" required minlength="2" maxlength="120" autocomplete="name" /></label>
          <label class="field"><span>Телефон *</span><input v-model="phone" required type="tel" inputmode="tel" autocomplete="tel" placeholder="+7 900 000-00-00" /></label>
          <label class="field"><span>E-mail</span><input v-model="email" type="email" maxlength="254" autocomplete="email" /></label>
          <label class="field"><span>Комментарий</span><textarea v-model="comment" rows="3" maxlength="2000" /></label>
          <label class="consent"><input v-model="consent" type="checkbox" required /><span>Я даю <a href="/privacy/#consent" target="_blank" rel="noopener">согласие на обработку персональных данных</a> и принимаю <a href="/privacy/" target="_blank" rel="noopener">политику обработки персональных данных</a></span></label>
          <p v-if="items.length === 0" class="inquiry-hint">Добавьте зеркало из каталога — заявка уедет менеджеру вместе с ним.</p>
          <p v-else-if="hasGone" class="inquiry-hint">Уберите товар, снятый с продажи, — тогда заявку можно отправить.</p>
          <button class="btn inquiry-submit" :disabled="!canSend" type="submit">{{ isSubmitting ? "Отправляем…" : "Отправить заявку" }} <span class="arrow" aria-hidden="true">→</span></button>
          <p v-if="result !== null" class="inquiry-note" :class="{ error: result.isError }" aria-live="polite">{{ result.text }}</p>
        </form>
      </template>
    </aside>
  </div>
</template>
