/* globals Quasar, Vue, _, VueQrcode, windowMixin, LNbits, LOCALE */

Vue.component(VueQrcode.name, VueQrcode)

var mapJukebox = obj => {
  if (obj.sp_device) {
    obj._data = _.clone(obj)

    obj.sp_id = obj._data.id
    obj.device = obj._data.sp_device.split('-')[0]
    playlists = obj._data.sp_playlists.split(',')
    var i
    playlistsar = []
    for (i = 0; i < playlists.length; i++) {
      playlistsar.push(playlists[i].split('-')[0])
    }
    obj.playlist = playlistsar.join()
    return obj
  } else {
    return
  }
}

new Vue({
  el: '#vue',
  mixins: [windowMixin],
  data() {
    return {
      JukeboxTable: {
        columns: [
          {
            name: 'title',
            align: 'left',
            label: 'Title',
            field: 'title'
          },
          {
            name: 'device',
            align: 'left',
            label: 'Device',
            field: 'device'
          },
          {
            name: 'playlist',
            align: 'left',
            label: 'Playlist',
            field: 'playlist'
          },
          {
            name: 'price',
            align: 'left',
            label: 'Price',
            field: 'price'
          }
        ],
        pagination: {
          rowsPerPage: 10
        }
      },
      isPwd: true,
      tokenFetched: true,
      devices: [],
      filter: '',
      jukebox: {},
      playlists: [],
      JukeboxLinks: [],
      step: 1,
      locationcbPath: '',
      locationcb: '',
      jukeboxDialog: {
        show: false,
        data: {}
      },
      spotifyDialog: false,
      qrCodeDialog: {
        show: false,
        data: null
      }
    }
  },
  computed: {},

  methods: {
    openQrCodeDialog(linkId) {
      const link = this.JukeboxLinks.find(link => link.id === linkId)
      this.qrCodeDialog.data = {...link}
      this.qrCodeDialog.data.url = `${window.location.protocol}//${window.location.host}`
      this.qrCodeDialog.show = true
    },

    async getJukeboxes() {
      try {
        const response = await LNbits.api.request(
          'GET',
          '/jukebox/api/v1/jukebox',
          this.g.user.wallets[0].adminkey
        )
        this.JukeboxLinks = response.data.map(obj => mapJukebox(obj))
      } catch (error) {
        console.error('Error in getJukeboxes:', error)
      }
    },

    async deleteJukebox(jukeId) {
      try {
        await LNbits.utils
          .confirmDialog('Are you sure you want to delete this Jukebox?')
          .onOk(async () => {
            await LNbits.api.request(
              'DELETE',
              `/jukebox/api/v1/jukebox/${jukeId}`,
              this.g.user.wallets[0].adminkey
            )
            this.getJukeboxes()
          })
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    async updateJukebox(linkId) {
      const link = this.JukeboxLinks.find(link => link.id === linkId)
      this.jukeboxDialog.data = {...link._data}
      await this.refreshDevices() // Ensure refreshDevices completes before moving to the next line
      await this.refreshPlaylists() // Ensure refreshPlaylists completes before moving to the next line
      console.log(this.devices)
      this.step = 4
      this.jukeboxDialog.data.sp_device = []
      this.jukeboxDialog.data.sp_playlists = []
      this.jukeboxDialog.data.sp_id = this.jukeboxDialog.data.id
      this.jukeboxDialog.data.price = String(this.jukeboxDialog.data.price)
      this.jukeboxDialog.show = true
    },

    closeFormDialog() {
      this.jukeboxDialog.data = {}
      this.jukeboxDialog.show = false
      this.step = 1
    },

    async submitSpotifyKeys() {
      this.jukeboxDialog.data.user = this.g.user.id
      try {
        const response = await LNbits.api.request(
          'POST',
          '/jukebox/api/v1/jukebox/',
          this.g.user.wallets[0].adminkey,
          this.jukeboxDialog.data
        )
        if (response.data) {
          this.jukeboxDialog.data.sp_id = response.data.id
          this.step = 3
        }
      } catch (error) {
        LNbits.utils.notifyApiError(error)
      }
    },

    authAccess() {
      this.requestAuthorization()
      this.getSpotifyTokens()
      this.$q.notify({
        spinner: true,
        message: 'Processing',
        timeout: 10000
      })
    },

    async getSpotifyTokens() {
      let counter = 0
      const timerId = setInterval(async () => {
        counter++
        if (!this.jukeboxDialog.data.sp_user) {
          clearInterval(timerId)
        }
        try {
          const response = await LNbits.api.request(
            'GET',
            `/jukebox/api/v1/jukebox/${this.jukeboxDialog.data.sp_id}`,
            this.g.user.wallets[0].adminkey
          )
          if (response.data.sp_access_token) {
            this.fetchAccessToken(response.data.sp_access_token)
            if (this.jukeboxDialog.data.sp_access_token) {
              this.refreshPlaylists()
              await this.refreshDevices()
              setTimeout(() => {
                if (this.devices.length < 1 || this.playlists.length < 1) {
                  this.$q.notify({
                    spinner: true,
                    color: 'red',
                    message:
                      'Error! Make sure Spotify is open on the device you wish to use, has playlists, and is playing something',
                    timeout: 10000
                  })
                  LNbits.api.request(
                    'DELETE',
                    `/jukebox/api/v1/jukebox/${response.data.id}`,
                    this.g.user.wallets[0].adminkey
                  )
                  this.getJukeboxes()
                  clearInterval(timerId)
                  this.closeFormDialog()
                } else {
                  this.step = 4
                  clearInterval(timerId)
                }
              }, 2000)
            }
          }
        } catch (error) {
          LNbits.utils.notifyApiError(error)
        }
      }, 3000)
    },

    requestAuthorization() {
      const url = 'https://accounts.spotify.com/authorize'
      const scope = [
        'user-read-private',
        'user-read-email',
        'user-modify-playback-state',
        'user-read-playback-position',
        'user-library-read',
        'streaming',
        'user-read-playback-state',
        'user-read-recently-played',
        'playlist-read-private'
      ].join(' ')
      const redirectUri = encodeURI(
        `${this.locationcbPath}${this.jukeboxDialog.data.sp_id}`
      )
      window.open(
        `${url}?client_id=${this.jukeboxDialog.data.sp_user}&response_type=code&redirect_uri=${redirectUri}&show_dialog=true&scope=${scope}`
      )
    },

    openNewDialog() {
      this.jukeboxDialog.show = true
      this.jukeboxDialog.data = {}
    },

    async createJukebox() {
      this.jukeboxDialog.data.sp_playlists =
        this.jukeboxDialog.data.sp_playlists.join()
      await this.updateDB()
      this.jukeboxDialog.show = false
      this.getJukeboxes()
    },

    async updateDB() {
      try {
        await LNbits.api.request(
          'PUT',
          `/jukebox/api/v1/jukebox/${this.jukeboxDialog.data.sp_id}`,
          this.g.user.wallets[0].adminkey,
          this.jukeboxDialog.data
        )
        if (
          this.jukeboxDialog.data.sp_playlists &&
          this.jukeboxDialog.data.sp_devices
        ) {
          this.getJukeboxes()
          // this.JukeboxLinks.push(mapJukebox(response.data));
        }
      } catch (error) {
        console.error('Error in updateDB:', error)
      }
    },

    async playlistApi(method, url, body) {
      try {
        const response = await fetch(url, {
          method,
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Bearer ' + this.jukeboxDialog.data.sp_access_token
          },
          body: body ? JSON.stringify(body) : null
        })

        if (response.status === 401) {
          await this.refreshAccessToken()
          await this.playlistApi(
            'GET',
            'https://api.spotify.com/v1/me/playlists',
            null
          )
          return // Exit to prevent further processing in case of token refresh
        }

        const responseObj = await response.json()
        this.jukeboxDialog.data.playlists = responseObj.items.map(
          item => `${item.name}-${item.id}`
        )
        this.playlists = [...this.jukeboxDialog.data.playlists]
      } catch (error) {
        console.error('Error in playlistApi:', error)
      }
    },

    refreshPlaylists() {
      this.playlistApi('GET', 'https://api.spotify.com/v1/me/playlists', null)
    },

    async deviceApi(method, url, body) {
      try {
        const response = await fetch(url, {
          method,
          headers: {
            'Content-Type': 'application/json',
            Authorization: 'Bearer ' + this.jukeboxDialog.data.sp_access_token
          },
          body: body ? JSON.stringify(body) : null
        })
        if (response.status === 401) {
          await this.refreshAccessToken()
          await this.deviceApi(
            'GET',
            'https://api.spotify.com/v1/me/player/devices',
            null
          )
          return // Exit to prevent further processing in case of token refresh
        }

        const responseObj = await response.json()
        this.jukeboxDialog.data.devices = responseObj.devices.map(
          device => `${device.name}-${device.id}`
        )
        this.devices = [...this.jukeboxDialog.data.devices]
      } catch (error) {
        console.error('Error in deviceApi:', error)
      }
    },

    async refreshDevices() {
      await this.deviceApi(
        'GET',
        'https://api.spotify.com/v1/me/player/devices',
        null
      )
    },

    async fetchAccessToken(code) {
      let body = 'grant_type=authorization_code'
      body += `&code=${code}`
      body += `&redirect_uri=${encodeURI(
        this.locationcbPath + this.jukeboxDialog.data.sp_id
      )}`
      await this.callAuthorizationApi(body)
    },

    async refreshAccessToken() {
      let body = 'grant_type=refresh_token'
      body += `&refresh_token=${this.jukeboxDialog.data.sp_refresh_token}`
      body += `&client_id=${this.jukeboxDialog.data.sp_user}`
      await this.callAuthorizationApi(body)
    },

    async callAuthorizationApi(body) {
      try {
        const response = await fetch('https://accounts.spotify.com/api/token', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            Authorization:
              'Basic ' +
              btoa(
                `${this.jukeboxDialog.data.sp_user}:${this.jukeboxDialog.data.sp_secret}`
              )
          },
          body: body
        })

        const responseObj = await response.json()
        if (responseObj.access_token) {
          this.jukeboxDialog.data.sp_access_token = responseObj.access_token
          this.jukeboxDialog.data.sp_refresh_token = responseObj.refresh_token
          this.updateDB()
        }
      } catch (error) {
        console.error('Error in callAuthorizationApi:', error)
      }
    }
  },
  created() {
    var getJukeboxes = this.getJukeboxes
    getJukeboxes()
    this.selectedWallet = this.g.user.wallets[0]
    this.locationcbPath = String(
      [
        window.location.protocol,
        '//',
        window.location.host,
        '/jukebox/api/v1/jukebox/spotify/cb/'
      ].join('')
    )
    this.locationcb = this.locationcbPath
  }
})
