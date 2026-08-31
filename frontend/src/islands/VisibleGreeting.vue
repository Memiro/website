<script setup lang="ts">
import { ref } from "vue";

const isVisible = ref(false);
</script>

<template>
  <section class="island-demo">
    <p>{{ isVisible ? "Остров загружен в области видимости." : "Прокрутите до этого острова." }}</p>
    <button type="button" @click="isVisible = true">Проверить остров</button>
  </section>
</template>
