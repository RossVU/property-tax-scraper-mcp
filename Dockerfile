FROM mcr.microsoft.com/dotnet/sdk:8.0.410 AS build-env
WORKDIR /app
RUN dotnet nuget add source https://nugetgallery.redchimney.com/api/v2 -n VuNugetGallery

ENV DOTNET_CLI_TELEMETRY_OPTOUT 1

# copy everything else and build
COPY . ./
RUN dotnet publish src/MyQueueContacts.Web -c Release -o out

# build runtime image
FROM harbor.redchimney.com/dockerhub/mrcenter/dpa-aspnetbase:2.4.2
WORKDIR /app
RUN printf -- "-----BEGIN CERTIFICATE----- \nMIIFjzCCA3egAwIBAgIQI5tC9qOmRqZDVzZUlrwtGzANBgkqhkiG9w0BAQsFADBa \nMQswCQYDVQQGEwJVUzEXMBUGA1UEChMOVmV0ZXJhbnNVbml0ZWQxHTAbBgNVBAsT \nFENlcnRpZmljYXRlQXV0aG9yaXR5MRMwEQYDVQQDEwpWVS1ST09ULUNBMB4XDTE2 \nMDMxNjE1MjAxMFoXDTMxMDMxNjE1MzAwOFowWjELMAkGA1UEBhMCVVMxFzAVBgNV \nBAoTDlZldGVyYW5zVW5pdGVkMR0wGwYDVQQLExRDZXJ0aWZpY2F0ZUF1dGhvcml0 \neTETMBEGA1UEAxMKVlUtUk9PVC1DQTCCAiIwDQYJKoZIhvcNAQEBBQADggIPADCC \nAgoCggIBALD35OGqaXeJHhdCCSr3gCEKc8p0vCrU8O/rpEmHA3mIgILpFxovSAhF \nAmemiyYK9CsmNrjeCa4/O/eBA7+ZqrOchCYj0DS0qO7jJ0GBHmvxuFbtPsZc4WG7 \nB0VDBG+kY1c84soytmuHE9TGnwC4WGpYtJvFVuIlpBj/z2vyVYh6Luzz6gYpwD9M \nlVxwviYB0UawXWwu5W8Jcnm1quVB5rA1BeqlS2avVLsixWRtomHOOWbV1fxYXe9E \ny9SOBzfKXXNkwBcE++N4eWNp5XobBshCnXjLm+eClOs8CRvqpea3VrrI5NyKpcMt \nlI1SZEMrOI3WAHtgDy7wXCM/dbH9WEUQvaKtPe7TnbYzScdluyaw3Y5XrtPeOyXq \nsbNQC6t7OKNj25ZJ2N0UJI2ZekcqjEKVIwbf/V5vMaT9YveWhsueAh9hDiIlEOjI \nIxjm6qUyoEplhRnBxkUGVjRpe+P+ujlU8cZZu1xHlhAB2lZEn09UVegVmY2DQcwF \n12mkOhJC1VdQXIDpbzkST0qG1vgSRcs7RICTnb3JmPRJOhUTNmlmr//MuLdVZYVn \nb+Pot3fo38GmZDV7Dj6luyIby3rFwEvnr15l/cFeRcg+n9emYyIMfGI4DyL7SeJM \nhyxcMpjwPe99H4hraUtEjGdq5XJpQBDtVhHfhby8l1WAtcQiw7O7AgMBAAGjUTBP \nMAsGA1UdDwQEAwIBhjAPBgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBRaAGSwmyDA \nAX30w6g7gfTnH2IDBjAQBgkrBgEEAYI3FQEEAwIBADANBgkqhkiG9w0BAQsFAAOC \nAgEAMZQxoZcrZ64pXjfAZ0pkHWZ1CB8KOjVb2+6/WrzbMpd9mndtFjSzCyOZQpDj \nNQpwL/O9pSsPKbjac4n5L2baH8lvCMgiq0e7h4+ade4yN77ZpIUBJTXqvIoz26WQ \nZIohysFMsJBn+th5x3GYyZZ4VpMYWsnSgCp8HAII57ursnRHXy5OPJW1KIBID3S+ \nmrxb8pQ4iI3d2BUy+s8rlWjUnJn0c6XPM88kv08zTNgrBrTmitCR4BSzJNhwUnHA \nbKfCYC7IyPDl6LQqa3cHxdUb4r24bOl9skzcAL4ywWNeVjgrHfLRMgx/J53wrefZ \ndJ56mVP+8yPD3AwzL6B1IF67v/nS4X78FxRK/Gn38nuxHTl+K2PuscrfrtDHQZTh \nvauHvdNfbnqitUB9hEPmxHihAV6JKom8LVAjTeaPhsxunXTkrJDPkgRAI96PSxSi \ntWuaZR+ult+CTB/VpCQajqHpi6q7TIwKM423yHBDujysQ16pACdv4Qiqyxo9rw7z \nmE0DiFLjR60PZiS/gmBHrO64+4tM0qQ28rI88zOrlklLX43V1BnXPojGntQkoR03 \n7EVGpAosMKXcJ67Jzer5ciTwdJZzZ7Hahns5yQS9Uht2lK4DTBVz2xY6KWNvCpnw \nssHy178QW/gr6fWCI+7XpNdsYU9K2fbBva331YIqpcB2HFM= \n-----END CERTIFICATE-----"> /usr/local/share/ca-certificates/vu-bundle.crt
RUN update-ca-certificates

# Setup for kerberos sidecar
COPY krb5.conf /etc/krb5.conf
RUN DEBIAN_FRONTEND=noninteractive apt-get update \
    && apt-get install -y --no-install-recommends krb5-config krb5-user \
    && rm -rf /var/lib/apt/lists/*

ENV ASPNETCORE_URLS "http://*:8080"
RUN useradd --system --no-create-home --shell /usr/sbin/nologin app-user

USER app-user
RUN mkdir -p /tmp/krb_ccache

COPY --from=build-env /app/out .
ENTRYPOINT ["dotnet", "CrmOpportunities.Web.dll"]
