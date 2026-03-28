<script setup lang="ts">
import { useWizardStore } from '@/stores/wizard'
import Textarea from '@/components/ui/Textarea.vue'
import Label from '@/components/ui/Label.vue'

const wizard = useWizardStore()
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
        <p class="text-xs text-muted-foreground">{{ $t('wizard.content.competitorsHint') }}</p>
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
        <div class="space-y-3">
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
              placeholder="Warm oranges, soft greens, and clean whites. Avoids dark or moody tones."
            />
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
