import { defineConfig } from 'orval'

export default defineConfig({
  omedia: {
    input: {
      target: './src/api/openapi.json',
    },
    output: {
      target: './src/api/generated/omedia.ts',
      schemas: './src/api/generated/model',
      mode: 'tags-split',
      client: 'fetch',
      httpClient: 'fetch',
      clean: true,
      override: {
        mutator: {
          path: './src/api/transport.ts',
          name: 'apiRequest',
        },
        fetch: {
          includeHttpResponseReturnType: false,
        },
      },
    },
  },
})
