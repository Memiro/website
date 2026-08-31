<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { calculate, type ProductCard } from "../lib/catalog-api";
import { calculatorStateForVariant, initialCalculatorState, pricePresentation, toCalculateRequest } from "../lib/calculator-state";

const props = defineProps<{ product: ProductCard }>();
const state = ref(initialCalculatorState(props.product));
const result = ref<ReturnType<typeof pricePresentation> | null>(null);
const isLoading = ref(false);

const selectionsByAttribute = computed(() => new Map(state.value.selections.map((selection) => [selection.attributeId, selection])));

function selectValue(attributeId: string, valueId: string): void {
  state.value.selections = state.value.selections.filter((selection) => selection.attributeId !== attributeId);
  state.value.selections.push({ attributeId, valueId, quantity: null });
}

function setQuantity(attributeId: string, quantity: string): void {
  state.value.selections = state.value.selections.filter((selection) => selection.attributeId !== attributeId);
  state.value.selections.push({ attributeId, valueId: null, quantity });
}

function selectVariant(index: number): void {
  state.value = calculatorStateForVariant(props.product, index);
  void refreshPrice();
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

async function refreshPrice(): Promise<void> {
  isLoading.value = true;
  try {
    result.value = pricePresentation(await calculate(toCalculateRequest(props.product.id, state.value)));
  } catch {
    result.value = {
      kind: "unavailable",
      total: null,
      message: "Не удалось рассчитать стоимость. Попробуйте ещё раз.",
      deltas: [],
    };
  }
  finally { isLoading.value = false; }
}

onMounted(() => { void refreshPrice(); });
</script>

<template>
  <section class="calc">
    <h2>Расчёт по вашим размерам</h2>
    <div class="calc-fields">
      <label v-if="product.variants.length > 1" class="field"><span>Готовый размер</span><select @change="selectVariant(Number(($event.target as HTMLSelectElement).value))"><option v-for="(variant, index) in product.variants" :key="`${variant.width_mm}-${variant.height_mm}-${index}`" :value="index">{{ variant.width_mm }} × {{ variant.height_mm }} мм</option></select></label>
      <label class="field"><span>Ширина, мм</span><input v-model.number="state.widthMm" type="number" min="1" inputmode="numeric" @change="refreshPrice" /></label>
      <label class="field"><span>Высота, мм</span><input v-model.number="state.heightMm" type="number" min="1" inputmode="numeric" @change="refreshPrice" /></label>
      <label v-for="attribute in product.attributes.filter((attribute) => attribute.values.length > 0)" :key="attribute.id" class="field"><span>{{ attribute.name }}</span><select :value="selectionsByAttribute.get(attribute.id)?.valueId ?? ''" @change="selectValue(attribute.id, ($event.target as HTMLSelectElement).value); refreshPrice()"><option v-for="value in attribute.values.filter((value) => value.id !== null)" :key="value.id" :value="value.id">{{ value.name }}</option></select></label>
      <label v-for="attribute in product.attributes.filter((attribute) => attribute.values.length === 0)" :key="attribute.id" class="field"><span>{{ attribute.name }}</span><input :value="selectionsByAttribute.get(attribute.id)?.quantity ?? ''" type="number" min="0" inputmode="decimal" @change="setQuantity(attribute.id, ($event.target as HTMLInputElement).value); refreshPrice()" /></label>
    </div>
    <div class="calc-result" aria-live="polite">
      <p v-if="isLoading" class="calc-note">Считаем стоимость…</p>
      <template v-else-if="result"><template v-if="result.kind === 'priced'"><strong class="calc-total">{{ Number(result.total).toLocaleString('ru-RU') }} ₽</strong><ul v-if="result.deltas.length > 0" class="calc-additions"><li v-for="delta in result.deltas" :key="`${delta.attributeId}-${delta.valueId}`"><span>{{ deltaLabel(delta.attributeId, delta.valueId) }}</span><b>{{ formatAmount(delta.amount) }}</b></li></ul></template><p v-else class="calc-note">{{ result.message }}</p></template>
      <p v-else class="calc-note">Измените размер или материалы, чтобы увидеть стоимость.</p>
    </div>
  </section>
</template>
