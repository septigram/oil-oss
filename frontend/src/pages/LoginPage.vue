<template>
  <q-layout view="hHh lpR fFf">
    <q-page-container>
      <q-page class="flex flex-center bg-grey-2">
        <q-card flat bordered class="login-card">
          <q-card-section>
            <div class="text-h6 text-center">Ops Incident Ledger ログイン</div>
          </q-card-section>
          <q-card-section>
            <q-form class="q-gutter-md" @submit.prevent="submit">
              <q-input
                v-model="loginName"
                label="ログイン ID"
                outlined
                dense
                autocomplete="username"
                :rules="[requiredRule]"
              />
              <q-input
                v-model="password"
                label="パスワード"
                type="password"
                outlined
                dense
                autocomplete="current-password"
                :rules="[requiredRule]"
              />
              <div class="row justify-end">
                <q-btn
                  type="submit"
                  color="primary"
                  label="ログイン"
                  :loading="auth.loading"
                />
              </div>
            </q-form>
          </q-card-section>
        </q-card>
      </q-page>
    </q-page-container>
  </q-layout>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useQuasar } from 'quasar'
import { useAuthStore } from '@/stores/authStore'
import { formatApiError } from '@/utils/apiError'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const $q = useQuasar()

const loginName = ref('')
const password = ref('')
const requiredRule = (v: string | null | undefined) => !!v?.trim() || '必須項目です'

async function submit() {
  try {
    await auth.login(loginName.value.trim(), password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.replace(redirect)
  } catch (err: unknown) {
    $q.notify({ type: 'negative', message: formatApiError(err, 'ログインに失敗しました') })
  }
}
</script>

<style scoped>
.login-card {
  width: 100%;
  max-width: 360px;
}
</style>
