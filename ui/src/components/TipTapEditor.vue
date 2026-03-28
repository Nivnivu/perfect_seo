<script setup lang="ts">
import { watch, onBeforeUnmount } from 'vue'
import { useEditor, EditorContent } from '@tiptap/vue-3'
import StarterKit from '@tiptap/starter-kit'
import Link from '@tiptap/extension-link'
import Placeholder from '@tiptap/extension-placeholder'
import TextAlign from '@tiptap/extension-text-align'
import {
  Bold, Italic, Heading2, Heading3,
  List, ListOrdered, Link2, Undo2, Redo2, AlignLeft, AlignRight,
} from 'lucide-vue-next'

const props = withDefaults(defineProps<{
  modelValue: string
  editable?: boolean
  placeholder?: string
}>(), {
  editable: true,
  placeholder: 'Start writing...',
})

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const editor = useEditor({
  content: props.modelValue,
  editable: props.editable,
  extensions: [
    StarterKit,
    Link.configure({ openOnClick: false, HTMLAttributes: { class: 'text-primary underline' } }),
    Placeholder.configure({ placeholder: props.placeholder }),
    TextAlign.configure({ types: ['heading', 'paragraph'] }),
  ],
  onUpdate({ editor }) {
    emit('update:modelValue', editor.getHTML())
  },
})

// Sync external modelValue changes (e.g. after AI refine)
watch(() => props.modelValue, (val) => {
  if (editor.value && editor.value.getHTML() !== val) {
    editor.value.commands.setContent(val, false)
  }
})

watch(() => props.editable, (val) => {
  editor.value?.setEditable(val)
})

onBeforeUnmount(() => editor.value?.destroy())

function setLink() {
  const url = window.prompt('Enter URL')
  if (!url) return
  editor.value?.chain().focus().setLink({ href: url }).run()
}
</script>

<template>
  <div class="tiptap-wrapper rounded-xl border border-input overflow-hidden bg-background">
    <!-- Toolbar -->
    <div v-if="editable" class="flex flex-wrap items-center gap-0.5 px-2 py-1.5 border-b border-border bg-muted/30">
      <button
        type="button"
        @click="editor?.chain().focus().toggleBold().run()"
        :class="editor?.isActive('bold') ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted'"
        class="p-1.5 rounded-md transition-colors"
        title="Bold"
      >
        <Bold class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        @click="editor?.chain().focus().toggleItalic().run()"
        :class="editor?.isActive('italic') ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted'"
        class="p-1.5 rounded-md transition-colors"
        title="Italic"
      >
        <Italic class="w-3.5 h-3.5" />
      </button>

      <div class="w-px h-4 bg-border mx-1" />

      <button
        type="button"
        @click="editor?.chain().focus().toggleHeading({ level: 2 }).run()"
        :class="editor?.isActive('heading', { level: 2 }) ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted'"
        class="p-1.5 rounded-md transition-colors"
        title="Heading 2"
      >
        <Heading2 class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        @click="editor?.chain().focus().toggleHeading({ level: 3 }).run()"
        :class="editor?.isActive('heading', { level: 3 }) ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted'"
        class="p-1.5 rounded-md transition-colors"
        title="Heading 3"
      >
        <Heading3 class="w-3.5 h-3.5" />
      </button>

      <div class="w-px h-4 bg-border mx-1" />

      <button
        type="button"
        @click="editor?.chain().focus().toggleBulletList().run()"
        :class="editor?.isActive('bulletList') ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted'"
        class="p-1.5 rounded-md transition-colors"
        title="Bullet list"
      >
        <List class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        @click="editor?.chain().focus().toggleOrderedList().run()"
        :class="editor?.isActive('orderedList') ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted'"
        class="p-1.5 rounded-md transition-colors"
        title="Ordered list"
      >
        <ListOrdered class="w-3.5 h-3.5" />
      </button>

      <div class="w-px h-4 bg-border mx-1" />

      <button
        type="button"
        @click="setLink"
        :class="editor?.isActive('link') ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted'"
        class="p-1.5 rounded-md transition-colors"
        title="Add link"
      >
        <Link2 class="w-3.5 h-3.5" />
      </button>

      <div class="w-px h-4 bg-border mx-1" />

      <button
        type="button"
        @click="editor?.chain().focus().setTextAlign('left').run()"
        :class="editor?.isActive({ textAlign: 'left' }) ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted'"
        class="p-1.5 rounded-md transition-colors"
        title="Align left"
      >
        <AlignLeft class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        @click="editor?.chain().focus().setTextAlign('right').run()"
        :class="editor?.isActive({ textAlign: 'right' }) ? 'bg-primary/10 text-primary' : 'text-muted-foreground hover:text-foreground hover:bg-muted'"
        class="p-1.5 rounded-md transition-colors"
        title="Align right (RTL)"
      >
        <AlignRight class="w-3.5 h-3.5" />
      </button>

      <div class="flex-1" />

      <button
        type="button"
        @click="editor?.chain().focus().undo().run()"
        :disabled="!editor?.can().undo()"
        class="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-30"
        title="Undo"
      >
        <Undo2 class="w-3.5 h-3.5" />
      </button>
      <button
        type="button"
        @click="editor?.chain().focus().redo().run()"
        :disabled="!editor?.can().redo()"
        class="p-1.5 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors disabled:opacity-30"
        title="Redo"
      >
        <Redo2 class="w-3.5 h-3.5" />
      </button>
    </div>

    <!-- Editor area -->
    <EditorContent :editor="editor" class="tiptap-content" />
  </div>
</template>

<style>
.tiptap-content .ProseMirror {
  outline: none;
  min-height: 400px;
  padding: 1rem 1.25rem;
  font-size: 0.9rem;
  line-height: 1.75;
  color: hsl(var(--foreground));
}
.tiptap-content .ProseMirror h1 { font-size: 1.5rem; font-weight: 700; margin: 1.25rem 0 0.5rem; }
.tiptap-content .ProseMirror h2 { font-size: 1.2rem; font-weight: 700; margin: 1rem 0 0.5rem; }
.tiptap-content .ProseMirror h3 { font-size: 1.05rem; font-weight: 600; margin: 0.75rem 0 0.4rem; }
.tiptap-content .ProseMirror p  { margin-bottom: 0.75rem; }
.tiptap-content .ProseMirror ul,
.tiptap-content .ProseMirror ol { padding-left: 1.5rem; margin-bottom: 0.75rem; }
.tiptap-content .ProseMirror li { margin-bottom: 0.25rem; }
.tiptap-content .ProseMirror a  { color: hsl(var(--primary)); text-decoration: underline; }
.tiptap-content .ProseMirror strong { font-weight: 700; }
.tiptap-content .ProseMirror em  { font-style: italic; }
.tiptap-content .ProseMirror p.is-editor-empty:first-child::before {
  content: attr(data-placeholder);
  color: hsl(var(--muted-foreground));
  pointer-events: none;
  float: left;
  height: 0;
}
</style>
