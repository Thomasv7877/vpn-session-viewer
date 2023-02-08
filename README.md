# Setup

# background

# deployment (Azure) example

# API usage

- get token
```
curl --location --request POST 'http://127.0.0.1:5000/api/loginUser' \
--header 'Authorization: Basic cHJvbW9uOjEyMzQ1'
```
- test token
```
curl --location --request GET 'http://127.0.0.1:5000/api/test' \
--header 'x-access-tokens: [token]'
```
- send monitoring message
```
curl --location --request POST 'http://127.0.0.1:5000/api/placeMessage' \
--header 'x-access-tokens: [token]' \
--header 'Content-Type: application/json' \
--data-raw '{
    "message" : "hello"
}'
```

# misc examples