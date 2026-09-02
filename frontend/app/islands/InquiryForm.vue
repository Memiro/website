<script setup lang="ts">
import { ref } from "vue";

import { inquiryErrorMessage, SubmitInquiryError, submitInquiry } from "./submit-inquiry.ts";
import { freeFormInquiry } from "../lib/inquiry-state.ts";

const name = ref("");
const phone = ref("");
const email = ref("");
const comment = ref("");
const consent = ref(false);
const isSubmitting = ref(false);
const result = ref<{ text: string; isError: boolean } | null>(null);

async function send(): Promise<void> {
  isSubmitting.value = true;
  result.value = null;
  try {
    await submitInquiry(freeFormInquiry({
      name: name.value,
      phone: phone.value,
      email: email.value,
      consent: consent.value,
    }, comment.value));
    name.value = "";
    phone.value = "";
    email.value = "";
    comment.value = "";
    consent.value = false;
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
</script>

<template>
  <form class="inquiry-form" @submit.prevent="send">
    <label class="field"><span>Ваше имя *</span><input v-model="name" required minlength="2" maxlength="120" autocomplete="name" /></label>
    <label class="field"><span>Телефон *</span><input v-model="phone" required type="tel" inputmode="tel" autocomplete="tel" placeholder="+7 900 000-00-00" /></label>
    <label class="field"><span>E-mail</span><input v-model="email" type="email" maxlength="254" autocomplete="email" /></label>
    <label class="field"><span>Комментарий</span><textarea v-model="comment" rows="3" maxlength="2000" /></label>
    <!-- Never pre-ticked: Роскомнадзор does not accept a pre-ticked consent (ст. 9 152-ФЗ). -->
    <label class="consent"><input v-model="consent" type="checkbox" required /><span>Я даю <a href="/privacy/#consent" target="_blank" rel="noopener">согласие на обработку персональных данных</a> и принимаю <a href="/privacy/" target="_blank" rel="noopener">политику обработки персональных данных</a></span></label>
    <button class="btn btn-primary inquiry-submit" :disabled="isSubmitting" type="submit">{{ isSubmitting ? "Отправляем…" : "Отправить заявку" }}</button>
    <p v-if="result !== null" class="inquiry-note" :class="{ error: result.isError }" aria-live="polite">{{ result.text }}</p>
  </form>
</template>
