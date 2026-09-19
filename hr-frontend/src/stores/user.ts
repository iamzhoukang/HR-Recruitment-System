import { defineStore } from 'pinia'

export interface Department {
    id: string
    name: string
}

export interface User {
    id: string
    username: string
    email: string
    phone_number: string | null
    realname: string
    department: Department 
    is_active: boolean
    is_superuser: boolean
    is_hr : boolean
    created_at: string
    managed_departments?: Department[] //HR负责的部门
}

export interface UserState {
    user: User | null
    accessToken: string | null
}

export const useUserStore = defineStore('user', {
    state: (): UserState =>{
        // 数据是存储在浏览器的localStorage中，所以在初始化时需要从localStorage中读取数据
        const user = localStorage.getItem('user')
        const accessToken = localStorage.getItem('accessToken')
        return {
            user: user ? JSON.parse(user) : null,
            accessToken: accessToken || null
        }
    },

    getters: {
        isLoggedIn(): boolean {
            return !!this.accessToken
        },

        getUserInfo(): User | null {
            return this.user
        },

        getAccessToken(): string | null {
            return this.accessToken
        },
        isHR(): boolean {
            return this.user?.is_hr || false
        },
        isSuperUser(): boolean {
            return this.user?.is_superuser || false
        }
    },

    actions: {
        login(user: User, accessToken: string) {
            this.user = user
            this.accessToken = accessToken
            // 将数据存储在localStorage中
            localStorage.setItem('user', JSON.stringify(user))
            localStorage.setItem('accessToken', accessToken)
        },

        logout() {
            this.user = null
            this.accessToken = null
            // 清除localStorage中的数据
            localStorage.removeItem('user')
            localStorage.removeItem('accessToken')
        },
        
    }
})