<script setup lang="ts">
import { ref } from 'vue'
import axios from 'axios'
import { useWizardStore } from '@/stores/wizard'
import Textarea from '@/components/ui/Textarea.vue'
import Label from '@/components/ui/Label.vue'
import { ImagePlus, X, Loader2 } from 'lucide-vue-next'

const wizard = useWizardStore()

const logoPreview = ref<string | null>(null)
const logoUploading = ref(false)
const logoError = ref('')

async function onLogoFile(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0]
  if (!file) return
  logoError.value = ''
  logoUploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const { data } = await axios.post('/api/upload/logo', form)
    wizard.form.brand_logo_path = data.path
    logoPreview.value = URL.createObjectURL(file)
  } catch (err: any) {
    logoError.value = err.response?.data?.detail ?? 'Upload failed'
  } finally {
    logoUploading.value = false
  }
}

function removeLogo() {
  wizard.form.brand_logo_path = ''
  logoPreview.value = null
  logoError.value = ''
}
</script>

<template>
  <div>
    <div class="mb-6">
      <h2 class="text-xl font-bold text-foreground">{{ $t('wizard.content.title') }}</h2>
      <p class="text-muted-foreground mt-1 text-sm">{{ $t('wizard.content.subtitle') }}</p>
    </div>

    <div class="space-y-6">

      <!-- Seed Keywords -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between">
          <Label>{{ $t('wizard.content.seedKeywords') }}</Label>
          <span class="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">{{ $t('wizard.content.optional') }}</span>
        </div>
        <Textarea
          v-model="wizard.form.seed_keywords"
          :rows="4"
          placeholder="dog food&#10;cat food&#10;pet accessories&#10;organic pet treats"
        />
        <p class="text-xs text-muted-foreground">{{ $t('wizard.content.seedKeywordsHint') }}</p>
      </div>

      <!-- Competitors -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between">
          <Label>{{ $t('wizard.content.competitors') }}</Label>
          <span class="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">{{ $t('wizard.content.optional') }}</span>
        </div>
        <Textarea
          v-model="wizard.form.competitors"
          :rows="3"
          placeholder="https://competitor1.com/&#10;https://competitor2.com/"
        />
        <p class="text-xs text-muted-foreground">
          {{ $t('wizard.content.competitorsHint') }}
          <span class="text-primary font-medium"> Additional competitors are discovered automatically from Google SERP results for each keyword.</span>
        </p>
      </div>

      <!-- Brand Voice -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between">
          <Label>{{ $t('wizard.content.brandVoice') }}</Label>
          <span class="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">{{ $t('wizard.content.optional') }}</span>
        </div>
        <Textarea
          v-model="wizard.form.brand_voice"
          :rows="4"
          placeholder="We are a friendly, expert pet care brand. Our tone is warm, informative, and trustworthy. We write for pet owners who care deeply about their animals..."
        />
        <p class="text-xs text-muted-foreground">{{ $t('wizard.content.brandVoiceHint') }}</p>
      </div>

      <!-- Image Style -->
      <div class="border-t border-border pt-5">
        <p class="text-sm font-semibold text-foreground mb-4">
          {{ $t('wizard.content.imageStyle') }}
          <span class="text-muted-foreground font-normal text-xs ms-2">{{ $t('wizard.content.imageStyleSubtitle') }}</span>
        </p>
        <div class="space-y-4">

          <!-- Brand Logo Upload -->
          <div class="space-y-2">
            <Label>Brand Logo <span class="text-xs text-muted-foreground font-normal">(composited onto generated images)</span></Label>

            <!-- Preview state -->
            <div v-if="logoPreview || wizard.form.brand_logo_path" class="flex items-center gap-3 p-3 rounded-lg border border-border bg-muted/30">
              <img
                v-if="logoPreview"
                :src="logoPreview"
                alt="Logo preview"
                class="w-12 h-12 object-contain rounded"
              />
              <div v-else class="w-12 h-12 rounded bg-muted flex items-center justify-center">
                <ImagePlus class="w-5 h-5 text-muted-foreground" />
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-xs font-medium text-foreground truncate">{{ wizard.form.brand_logo_path }}</p>
                <p class="text-xs text-muted-foreground">Saved to project folder</p>
              </div>
              <button type="button" @click="removeLogo" class="text-muted-foreground hover:text-destructive transition-colors">
                <X class="w-4 h-4" />
              </button>
            </div>

            <!-- Upload area -->
            <label v-else class="flex items-center gap-3 px-4 py-3 rounded-lg border border-dashed border-border hover:border-primary/50 hover:bg-muted/30 cursor-pointer transition-colors">
              <Loader2 v-if="logoUploading" class="w-5 h-5 text-muted-foreground animate-spin" />
              <ImagePlus v-else class="w-5 h-5 text-muted-foreground" />
              <span class="text-sm text-muted-foreground">
                {{ logoUploading ? 'Uploading...' : 'Click to upload PNG, JPEG, WebP or SVG (max 2 MB)' }}
              </span>
              <input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" class="hidden" @change="onLogoFile" :disabled="logoUploading" />
            </label>

            <p v-if="logoError" class="text-xs text-destructive">{{ logoError }}</p>
          </div>

          <div class="space-y-1.5">
            <Label>{{ $t('wizard.content.imageDescription') }}</Label>
            <Textarea
              v-model="wizard.form.image_description"
              :rows="2"
              placeholder="A modern pet care brand with bright, friendly visuals featuring happy pets and their owners"
            />
          </div>
          <div class="space-y-1.5">
            <Label>{{ $t('wizard.content.visualElements') }}</Label>
            <Textarea
              v-model="wizard.form.image_visual_elements"
              :rows="2"
              placeholder="Clean backgrounds, natural lighting, dogs and cats as main subjects, lifestyle photography style"
            />
          </div>
          <div class="space-y-1.5">
            <Label>{{ $t('wizard.content.colorPalette') }}</Label>
            <Textarea
              v-model="wizard.form.image_color_palette"
              :rows="2"
              placeholder="Warm orange #FF6B35, soft green #4CAF82, clean white #FFFFFF. Avoid dark or moody tones."
            />
            <p class="text-xs text-muted-foreground">Include hex codes for precise color control in generated images.</p>
          </div>
        </div>
      </div>

      <!-- Unique Selling Points -->
      <div class="space-y-1.5">
        <div class="flex items-center justify-between">
          <Label>{{ $t('wizard.content.usp') }}</Label>
          <span class="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded">{{ $t('wizard.content.optional') }}</span>
        </div>
        <Textarea
          v-model="wizard.form.unique_selling_points"
          :rows="3"
          placeholder="Free shipping on orders over $50&#10;Vet-approved products only&#10;30-day return guarantee"
        />
        <p class="text-xs text-muted-foreground">{{ $t('wizard.content.uspHint') }}</p>
      </div>

    </div>
  </div>
</template>
