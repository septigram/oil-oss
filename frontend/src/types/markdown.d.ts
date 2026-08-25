declare module 'markdown' {
  export const markdown: {
    toHTML: (source: string, dialect?: string) => string
  }
}
