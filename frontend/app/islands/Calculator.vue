<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { calculatePrice } from "./calculate-price.ts";
import { inquiryErrorMessage, SubmitInquiryError, submitInquiry } from "./submit-inquiry.ts";
import type { ProductCard } from "../lib/catalog-api.ts";
import { Calculator, HEIGHT_FIELD, WIDTH_FIELD } from "../lib/calculator-state.ts";
import {
  addInquiryItem,
  canAddCalculatorConfiguration,
  canShowInquiryEditor as isInquiryEditorVisible,
  inquiryItemFromCalculator,
  loadInquiryItems,
  removeInquiryItem,
  saveInquiryItems,
  selectionInquiry,
} from "../lib/inquiry-state.ts";
import type { InquiryItem } from "../lib/inquiry-state.ts";

const props = defineProps<{ product: ProductCard }>();
const calculator = reactive(new Calculator(props.product, calculatePrice));
const items = ref<InquiryItem[]>([]);
const wish = ref("");
const name = ref("");
const phone = ref("");
const email = ref("");
const consent = ref(false);
const submitResult = ref<{ text: string; isError: boolean } | null>(null);
const isSubmitting = ref(false);

const price = computed(() => (calculator.request.status === "done" ? calculator.request.price : null));
const canAddToInquiry = computed(() => canAddCalculatorConfiguration(price.value?.kind, wish.value));
const canShowInquiryEditor = computed(() => isInquiryEditorVisible(price.value?.kind));

function typed(event: Event): string {
  return (event.target as HTMLInputElement | HTMLSelectElement).value;
}

function deltaLabel(attributeId: string, valueId: string | null): string {
  const attribute = props.product.attributes.find((item) => item.id === attributeId);
  const value = attribute?.values.find((item) => item.id === valueId);
  return value?.name ?? attribute?.name ?? "Выбранная опция";
}

function formatAmount(amount: string): string {
  const value = Number(amount);
  return `${value > 0 ? "+" : ""}${value.toLocaleString("ru-RU")} ₽`;
}

function addToInquiry(): void {
  const priced = calculator.priced;
  const kind = price.value?.kind;
  if (priced === null || (kind !== "priced" && kind !== "wish")) {
    return;
  }
  items.value = addInquiryItem(
    window.localStorage,
    items.value,
    inquiryItemFromCalculator(props.product, priced, kind, wish.value),
  );
  wish.value = "";
  submitResult.value = null;
}

function removeItem(index: number): void {
  items.value = removeInquiryItem(window.localStorage, items.value, index);
}

async function sendInquiry(): Promise<void> {
  if (items.value.length === 0) {
    return;
  }
  isSubmitting.value = true;
  submitResult.value = null;
  try {
    await submitInquiry(selectionInquiry(items.value, {
      name: name.value,
      phone: phone.value,
      email: email.value,
      consent: consent.value,
    }));
    items.value = [];
    saveInquiryItems(window.localStorage, items.value);
    submitResult.value = { text: "Спасибо! Заявка отправлена, менеджер свяжется с вами.", isError: false };
  } catch (error) {
    submitResult.value = {
      text: error instanceof SubmitInquiryError
        ? inquiryErrorMessage(error)
        : "Не удалось отправить заявку. Попробуйте ещё раз.",
      isError: true,
    };
  } finally {
    isSubmitting.value = false;
  }
}

onMounted(() => {
  items.value = loadInquiryItems(window.localStorage);
  void calculator.refresh();
});
</script>

<template>
  <section class="calc">
    <h2>Расчёт по вашим размерам</h2>
    <div class="calc-fields">
      <label v-if="product.variants.length > 1" class="field"><span>Готовый размер</span><select :value="calculator.variantIndex ?? ''" @change="calculator.chooseVariant(Number(typed($event)))"><option v-if="calculator.variantIndex === null" value="" disabled>Свой размер</option><option v-for="(variant, index) in product.variants" :key="`${variant.width_mm}-${variant.height_mm}-${index}`" :value="index">{{ variant.width_mm }} × {{ variant.height_mm }} мм</option></select></label>
      <label class="field"><span>Ширина, мм</span><input :value="calculator.widthText" :class="{ invalid: calculator.isInvalid(WIDTH_FIELD) }" type="number" min="1" inputmode="numeric" @change="calculator.setWidth(typed($event))" /></label>
      <label class="field"><span>Высота, мм</span><input :value="calculator.heightText" :class="{ invalid: calculator.isInvalid(HEIGHT_FIELD) }" type="number" min="1" inputmode="numeric" @change="calculator.setHeight(typed($event))" /></label>
      <label v-for="attribute in product.attributes.filter((attribute) => attribute.values.length > 0)" :key="attribute.id" class="field"><span>{{ attribute.name }}</span><select :value="calculator.chosenValue(attribute.id)" @change="calculator.chooseValue(attribute.id, typed($event))"><option value="">Как в товаре</option><option v-for="value in attribute.values.filter((value) => value.id !== null)" :key="value.id" :value="value.id">{{ value.name }}</option></select></label>
      <label v-for="attribute in product.attributes.filter((attribute) => attribute.values.length === 0)" :key="attribute.id" class="field"><span>{{ attribute.name }}</span><input :value="calculator.chosenQuantity(attribute.id)" :class="{ invalid: calculator.isInvalid(attribute.id) }" type="text" inputmode="decimal" @change="calculator.setQuantity(attribute.id, typed($event))" /></label>
    </div>
    <div class="calc-result" aria-live="polite">
      <p v-if="calculator.request.status === 'loading'" class="calc-note">Считаем стоимость…</p>
      <p v-else-if="calculator.request.status === 'invalid'" class="calc-note">Проверьте выделенные поля: размер и количество должны быть числами.</p>
      <p v-else-if="calculator.request.status === 'error'" class="calc-note">Не удалось рассчитать стоимость. Попробуйте ещё раз.</p>
      <template v-else-if="price"><template v-if="price.kind === 'priced'"><strong class="calc-total">{{ Number(price.total).toLocaleString('ru-RU') }} ₽</strong><ul v-if="price.deltas.length > 0" class="calc-additions"><li v-for="delta in price.deltas" :key="`${delta.attributeId}-${delta.valueId}`"><span>{{ deltaLabel(delta.attributeId, delta.valueId) }}</span><b>{{ formatAmount(delta.amount) }}</b></li></ul></template><p v-else class="calc-note">{{ price.message }}</p></template>
      <p v-else class="calc-note">Измените размер или материалы, чтобы увидеть стоимость.</p>
    </div>
    <div v-if="canShowInquiryEditor" class="inquiry-item-editor">
      <label v-if="price?.kind === 'wish'" class="field"><span>Ваше пожелание</span><textarea v-model="wish" required rows="3" placeholder="Расскажите, каким должен быть этот размер" /></label>
      <button class="btn btn-primary inquiry-add" :disabled="!canAddToInquiry" type="button" @click="addToInquiry">Добавить в заявку</button>
    </div>
    <section v-if="items.length > 0 || submitResult !== null" class="inquiry-panel" aria-live="polite">
      <template v-if="items.length > 0">
        <h2>Ваша заявка</h2>
        <p class="muted">Каждая конфигурация уйдёт менеджеру отдельным техническим заданием.</p>
        <ul class="inquiry-items">
          <li v-for="(item, index) in items" :key="`${item.productId}-${index}`">
            <span><b>{{ item.productName }}</b><small>{{ item.widthMm }} × {{ item.heightMm }} мм<span v-if="item.isWish"> · индивидуальное пожелание</span></small></span>
            <button type="button" class="inquiry-remove" @click="removeItem(index)">Удалить</button>
          </li>
        </ul>
        <form class="inquiry-form" @submit.prevent="sendInquiry">
          <label class="field"><span>Ваше имя</span><input v-model="name" required autocomplete="name" /></label>
          <label class="field"><span>Телефон</span><input v-model="phone" required autocomplete="tel" inputmode="tel" /></label>
          <label class="field"><span>Email</span><input v-model="email" type="email" autocomplete="email" /></label>
          <label class="consent"><input v-model="consent" type="checkbox" required /><span>Согласен на <a href="/privacy/" target="_blank" rel="noopener">обработку персональных данных</a></span></label>
          <button class="btn btn-primary inquiry-submit" :disabled="isSubmitting" type="submit">{{ isSubmitting ? "Отправляем…" : "Отправить заявку" }}</button>
        </form>
      </template>
      <p v-if="submitResult !== null" class="inquiry-note" :class="{ error: submitResult.isError }">{{ submitResult.text }}</p>
    </section>
  </section>
</template>
