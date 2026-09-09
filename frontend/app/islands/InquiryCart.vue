<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { inquiryErrorMessage, SubmitInquiryError, submitInquiry } from "./submit-inquiry.ts";
import { notifyInquiryChanged } from "../lib/inquiry-events.ts";
import {
  loadInquiryItems,
  removeInquiryItem,
  saveInquiryItems,
  selectionInquiry,
} from "../lib/inquiry-state.ts";
import type { InquiryItem } from "../lib/inquiry-state.ts";

const items = ref<InquiryItem[]>([]);
const isLoaded = ref(false);
const name = ref("");
const phone = ref("");
const email = ref("");
const consent = ref(false);
const isSubmitting = ref(false);
const result = ref<{ text: string; isError: boolean } | null>(null);

const isEmpty = computed(() => isLoaded.value && items.value.length === 0);

function removeItem(index: number): void {
  items.value = removeInquiryItem(window.localStorage, items.value, index);
  notifyInquiryChanged(window);
}

async function send(): Promise<void> {
  if (items.value.length === 0) {
    return;
  }
  isSubmitting.value = true;
  result.value = null;
  try {
    await submitInquiry(selectionInquiry(items.value, {
      name: name.value,
      phone: phone.value,
      email: email.value,
      consent: consent.value,
    }));
    items.value = [];
    saveInquiryItems(window.localStorage, items.value);
    notifyInquiryChanged(window);
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

onMounted(() => {
  items.value = loadInquiryItems(window.localStorage);
  isLoaded.value = true;
});
</script>

<template>
  <div class="inquiry">
    <div>
      <ul v-if="items.length > 0" class="inquiry-items">
        <li v-for="(item, index) in items" :key="`${item.productId}-${index}`">
          <span>
            <b>{{ item.productName }}</b>
            <small>{{ item.widthMm }} × {{ item.heightMm }} мм<span v-if="item.isWish"> · индивидуальное пожелание</span></small>
            <span v-if="item.wish" class="muted">{{ item.wish }}</span>
          </span>
          <button class="inquiry-remove" type="button" @click="removeItem(index)">Удалить</button>
        </li>
      </ul>
      <div v-if="isEmpty" class="empty">
        <p class="sub">Пока пусто.</p>
        <a class="btn btn--ghost btn--sm" href="/catalog/">Перейти в каталог <span class="arrow" aria-hidden="true">→</span></a>
      </div>
    </div>
    <aside class="inquiry-panel">
      <h2>Оставить заявку</h2>
      <p class="muted">Отправим подборку менеджеру вместе с вашими контактами.</p>
      <form class="inquiry-form" @submit.prevent="send">
        <label class="field"><span>Ваше имя *</span><input v-model="name" required minlength="2" maxlength="120" autocomplete="name" /></label>
        <label class="field"><span>Телефон *</span><input v-model="phone" required type="tel" inputmode="tel" autocomplete="tel" placeholder="+7 900 000-00-00" /></label>
        <label class="field"><span>E-mail</span><input v-model="email" type="email" maxlength="254" autocomplete="email" /></label>
        <label class="consent"><input v-model="consent" type="checkbox" required /><span>Я даю <a href="/privacy/#consent" target="_blank" rel="noopener">согласие на обработку персональных данных</a> и принимаю <a href="/privacy/" target="_blank" rel="noopener">политику обработки персональных данных</a></span></label>
        <p v-if="items.length === 0" class="inquiry-hint">Добавьте зеркало из каталога — заявка уедет менеджеру вместе с ним.</p>
        <button class="btn inquiry-submit" :disabled="isSubmitting || items.length === 0" type="submit">{{ isSubmitting ? "Отправляем…" : "Отправить заявку" }} <span class="arrow" aria-hidden="true">→</span></button>
        <p v-if="result !== null" class="inquiry-note" :class="{ error: result.isError }" aria-live="polite">{{ result.text }}</p>
      </form>
    </aside>
  </div>
</template>
