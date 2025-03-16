# AI Payment Agent SDK

A Python SDK for AI agents to make payments on merchant websites that support the AI payment protocol.

## Installation

```bash
pip install agent-payment-client
```

## Requirements
* Python 3.7+
* cryptography
* aiohttp
* playwright

## Quick Start

The SDK supports two integration methods:
1. Direct payment flow
2. Webhook-based payment flow

### Direct Payment Flow

```python
import asyncio
from agent-payment-client import AgentPaymentClient

# Replace with your RSA private key
PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
YOUR_PRIVATE_KEY_HERE
-----END PRIVATE KEY-----"""

async def main():
    # Initialize the payment client
    client = AgentPaymentClient(
        agent_id="YOUR_AGENT_ID",
        private_key_pem=PRIVATE_KEY,
        payment_gateway_url="https://payment-gateway.example.com/api"
    )
    
    # Check if a website supports AI payments
    compatibility = await client.check_website_compatibility("https://merchant-example.com")
    
    if compatibility["compatible"]:
        merchant_id = compatibility["merchantId"]
        
        # Initiate a payment
        payment_response = await client.initiate_payment(
            merchant_id=merchant_id,
            amount=19.99,
            currency="USD",
            description="AI-assisted purchase",
            agent_payment_reference="order-12345"
        )
        
        print(f"Payment initiated: {payment_response}")
        
        # Later, complete the payment
        # (usually after merchant website confirmation, i.e. initialization)
        if payment_response:
            success = await client.complete_payment(
                payment_id=payment_response["payment_id"],
                merchant_id=merchant_id,
                encrypted_advice=payment_response["encrypted_advice"],
                secret=payment_response["secret"]
            )
            
            print(f"Payment completed: {success}")

if __name__ == "__main__":
    asyncio.run(main())
```

### Webhook-based Payment Flow

#### Part 1: Check Compatibility and Initiate Payment

```python
import asyncio
from agent-payment-client import AgentPaymentClient

# Replace with your RSA private key
PRIVATE_KEY = """-----BEGIN PRIVATE KEY-----
YOUR_PRIVATE_KEY_HERE
-----END PRIVATE KEY-----"""

async def start_payment():
    # Initialize the payment client
    client = AgentPaymentClient(
        agent_id="YOUR_AGENT_ID",
        private_key_pem=PRIVATE_KEY,
        payment_gateway_url="https://payment-gateway.example.com/api"
    )
    
    # Check if a website supports AI payments
    compatibility = await client.check_website_compatibility("https://merchant-example.com")
    
    if compatibility["compatible"]:
        merchant_id = compatibility["merchantId"]
        
        # Initiate a payment
        payment_response = await client.initiate_payment(
            merchant_id=merchant_id,
            amount=19.99,
            currency="USD",
            description="AI-assisted purchase",
            agent_payment_reference="order-12345"
        )
        
        print(f"Payment initiated: {payment_response}")
        # Payment completion will be handled by webhook

if __name__ == "__main__":
    asyncio.run(start_payment())
```

#### Part 2: Set Up Webhook for Payment Completion

Implement a webhook endpoint in your server application (e.g., using Flask or FastAPI):

```python
from flask import Flask, request, jsonify
from agent-payment-client import AgentPaymentClient

app = Flask(__name__)
client = AgentPaymentClient(
    agent_id="YOUR_AGENT_ID",
    private_key_pem=PRIVATE_KEY,
    payment_gateway_url="https://payment-gateway.example.com/api"
)

@app.route('/webhook/payment', methods=['POST'])
async def payment_webhook():
    data = request.json
    
    if data['status'] == 'initialized':
        # Complete the payment
        success = await client.complete_payment(
            merchant_id=data['merchant_id'],
            payment_id=data['payment_id'],
            encrypted_advice=data['encrypted_advice'],
            secret=data['secret']
        )
        return jsonify({"success": success})
    
    return jsonify({"success": True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

**Note**: Your webhook URL must be registered with the payment processing backend.

## Bill Payments and Bank Transfers

The SDK also supports bill payments and bank transfers:

```python
# Make a bill payment
bill_result = await client.make_bill_payment(
    merchant_id="MERCHANT_ID",
    parameters={
        "bill_type": "electricity",
        "provider": "NationalGrid",
        "account_number": "1234567890",
        "amount": 50.00,
        "reference": "March2025"
    }
)

# Make a bank transfer
transfer_result = await client.make_transfer(
    merchant_id="MERCHANT_ID",
    parameters={
        "amount": 100.00,
        "recipient": "Jane Doe",
        "bank_name": "Example Bank",
        "account_number": "0987654321",
        "reference": "Invoice #123"
    }
)
```

## API Reference

### `AgentPaymentClient`

The main class for interacting with the payment gateway.

#### Constructor

```python
client = AgentPaymentClient(
    agent_id: str,
    private_key_pem: str,
    payment_gateway_url: str
)
```

#### Methods

* `get_public_key_pem()` - Get the agent's public key in PEM format
* `check_website_compatibility(url: str)` - Check if a website supports AI payments
* `initiate_payment(merchant_id, amount, currency, description, agent_payment_reference)` - Start a payment
* `complete_payment(payment_id, merchant_id, encrypted_advice, secret)` - Complete a payment
* `make_bill_payment(merchant_id, parameters)` - Make a bill payment (utilities, etc.)
* `make_transfer(merchant_id, parameters)` - Make a bank transfer
* `check_initialization_status(agent_payment_reference)` - Check payment status

## Security

This SDK uses RSA public-key cryptography for secure communication with the payment gateway. Ensure that your private key is kept secure and never exposed in client-side code.

## Testing and General Usage

Due to the workload, there are currently no published tests for this SDK. However, you can learn how to set up and use this SDK alongside the other 2 components ([payment gateway backend](https://tally.so/r/wvKeg4) and [merchant frontend SDK](https://github.com/ibnahmadcoded/merchant-payment-client)) [here](https://github.com/ibnahmadcoded/agent-pay-intro).

## Community

Join our community on [Discord](https://discord.gg/6C3uwQb8) and follow us on LinkedIn and X. Feel free to contribute and raise issues. 

## License

MIT