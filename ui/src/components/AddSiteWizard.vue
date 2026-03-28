<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { X, Check } from 'lucide-vue-next'
import { useWizardStore } from '@/stores/wizard'
import StepPlatform      from './wizard/StepPlatform.vue'
import StepSiteInfo      from './wizard/StepSiteInfo.vue'
import StepCredentials   from './wizard/StepCredentials.vue'
import StepSearchConsole from './wizard/StepSearchConsole.vue'
import StepContent       from './wizard/StepContent.vue'
import StepReview        from './wizard/StepReview.vue'

const wizard = useWizardStore()
const { t } = useI18n()

const steps = computed(() => [
  { label: t('wizard.steps.platform.label'),      desc: t('wizard.steps.platform.desc'),      component: StepPlatform },
  { label: t('wizard.steps.siteInfo.label'),      desc: t('wizard.steps.siteInfo.desc'),      component: StepSiteInfo },
  { label: t('wizard.steps.credentials.label'),  desc: t('wizard.steps.credentials.desc'),  component: StepCredentials },
  { label: t('wizard.steps.searchConsole.label'), desc: t('wizard.steps.searchConsole.desc'), component: StepSearchConsole },
  { label: t('wizard.steps.content.label'),       desc: t('wizard.steps.content.desc'),       component: StepContent },
  { label: t('wizard.steps.review.label'),        desc: t('wizard.steps.review.desc'),        component: StepReview },
])

const stepError = computed({
  get: () => (wizard as any)._stepError ?? null,
  set: (v) => { (wizard as any)._stepError = v },
})

import { ref } from 'vue'
const stepErrorRef = ref<string | null>(null)

const currentComponent = computed(() => steps.value[wizard.currentStep].component)
const isLastStep = computed(() => wizard.currentStep === steps.value.length - 1)

function goToStep(i: number) {
  if (i <= wizard.currentStep) {
    wizard.currentStep = i
    stepErrorRef.value = null
  }
}

function prev() {
  if (wizard.currentStep > 0) {
    wizard.currentStep--
    stepErrorRef.value = null
  }
}

function next() {
  const err = wizard.validateStep(wizard.currentStep)
  if (err) {
    stepErrorRef.value = err
    return
  }
  stepErrorRef.value = null
  wizard.currentStep++
}

async function save() {
  await wizard.save()
}

function requestClose() {
  const f = wizard.form
  const dirty = f.site_id || f.site_name || f.domain || f.ai_api_key
  if (dirty && !confirm(t('wizard.discardConfirm'))) return
  wizard.close()
}

function onOverlayClick(e: MouseEvent) {
  if (e.target === e.currentTarget) requestClose()
}
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="wizard.isOpen"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        style="background: rgba(0,0,0,0.55); backdrop-filter: blur(4px);"
        @click="onOverlayClick"
      >
        <div
          class="bg-background rounded-2xl shadow-2xl w-full max-w-4xl flex overflow-hidden"
          style="height: 85vh; max-height: 800px;"
          @click.stop
        >
          <!-- ── Sidebar ─────────────────────────────────────── -->
          <div
            class="w-56 flex flex-col flex-shrink-0"
            style="background: hsl(var(--sidebar));"
          >
            <div class="px-5 py-5 border-b border-white/10">
              <h2 class="text-white font-bold text-sm leading-none">{{ $t('wizard.addNewSite') }}</h2>
              <p class="text-xs mt-1" style="color: hsl(var(--sidebar-foreground) / 0.45);">
                {{ $t('wizard.stepOf', { current: wizard.currentStep + 1, total: steps.length }) }}
              </p>
            </div>

            <nav class="flex-1 p-3 space-y-0.5 overflow-y-auto">
              <button
                v-for="(step, i) in steps"
                :key="i"
                type="button"
                @click="goToStep(i)"
                class="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-start transition-colors"
                :class="[
                  i === wizard.currentStep ? 'bg-white/10' : 'hover:bg-white/6',
                  i > wizard.currentStep ? 'opacity-40 cursor-default' : 'cursor-pointer',
                ]"
              >
                <div
                  class="w-6 h-6 rounded-full flex items-center justify-center flex-shrink-0 text-xs font-bold transition-all"
                  :class="
                    i < wizard.currentStep
                      ? 'bg-primary text-white'
                      : i === wizard.currentStep
                        ? 'border-2 border-primary text-primary bg-white/5'
                        : 'border-2 border-white/20 text-white/40'
                  "
                >
                  <Check v-if="i < wizard.currentStep" class="w-3 h-3" />
                  <span v-else>{{ i + 1 }}</span>
                </div>

                <div class="min-w-0">
                  <p
                    class="text-xs font-semibold leading-none truncate"
                    :class="i === wizard.currentStep ? 'text-white' : 'text-white/70'"
                  >{{ step.label }}</p>
                  <p
                    class="text-xs mt-0.5 truncate"
                    style="color: hsl(var(--sidebar-foreground) / 0.4)"
                  >{{ step.desc }}</p>
                </div>
              </button>
            </nav>

            <div class="px-4 py-4 border-t border-white/10">
              <p class="text-xs" style="color: hsl(var(--sidebar-foreground) / 0.3);">
                {{ $t('wizard.creates') }} <code class="text-xs">config.{{ wizard.form.site_id || '…' }}.yaml</code>
              </p>
            </div>
          </div>

          <!-- ── Content area ───────────────────────────────── -->
          <div class="flex-1 flex flex-col min-w-0">
            <!-- Close button -->
            <div class="flex justify-end px-6 pt-5 flex-shrink-0">
              <button
                type="button"
                @click="requestClose"
                class="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
              >
                <X class="w-4 h-4" />
              </button>
            </div>

            <!-- Scrollable step content -->
            <div class="flex-1 overflow-y-auto px-8 pb-6">
              <component :is="currentComponent" />
            </div>

            <!-- ── Footer ─────────────────────────────────── -->
            <div class="flex-shrink-0 border-t border-border px-8 py-4">
              <div
                v-if="stepErrorRef"
                class="flex items-center gap-2 text-destructive text-sm mb-3 bg-destructive/8 px-3 py-2 rounded-lg"
              >
                <span class="text-xs font-medium">{{ stepErrorRef }}</span>
              </div>

              <div class="flex items-center justify-between">
                <button
                  type="button"
                  @click="prev"
                  :disabled="wizard.currentStep === 0"
                  class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border border-border hover:bg-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                >
                  {{ $t('wizard.back') }}
                </button>

                <button
                  v-if="!isLastStep"
                  type="button"
                  @click="next"
                  class="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold bg-primary text-white hover:bg-primary/90 transition-colors shadow-sm"
                >
                  {{ $t('wizard.next') }}
                </button>
                <button
                  v-else
                  type="button"
                  @click="save"
                  :disabled="wizard.saving"
                  class="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-semibold bg-primary text-white hover:bg-primary/90 transition-colors shadow-sm disabled:opacity-60"
                >
                  <div v-if="wizard.saving" class="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <Check v-else class="w-4 h-4" />
                  {{ wizard.saving ? $t('wizard.saving') : $t('wizard.save') }}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-enter-active, .modal-leave-active {
  transition: opacity 0.2s ease;
}
.modal-enter-from, .modal-leave-to {
  opacity: 0;
}
.modal-enter-active > div,
.modal-leave-active > div {
  transition: transform 0.2s ease;
}
.modal-enter-from > div,
.modal-leave-to > div {
  transform: scale(0.97) translateY(8px);
}
</style>
