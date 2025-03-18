from email.policy import default
import aiohttp
import base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from playwright.async_api import async_playwright
from typing import Optional, Dict
import json
import hashlib


class AgentPaymentClient:
    """Client for AI agents to make payments on compatible merchant websites."""
    
    def __init__(
        self, 
        agent_id: str, 
        private_key_pem: str, 
        payment_gateway_url: str
    ):
        """
        Initialize a payment client for an AI agent.
        
        Args:
            agent_id: Unique identifier for the agent
            private_key_pem: PEM-formatted RSA private key
            payment_gateway_url: URL of the payment gateway API
        """
        self.agent_id = agent_id
        self.private_key = serialization.load_pem_private_key(
            private_key_pem.encode(),
            password=None
        )
        self.public_key = self.private_key.public_key()
        self.payment_gateway_url = payment_gateway_url  
    
    def get_public_key_pem(self) -> str:
        """Get the agent's public key in PEM format."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
    
    async def check_website_compatibility(self, url: str) -> dict:
        """
        Check if a website is compatible with AI payments.
        
        Args:
            url: Website URL to check
            
        Returns:
            Dictionary with compatibility status and merchant ID
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(url)
                await page.wait_for_selector('meta[data-ai-payments="enabled"]', state="attached")
                
                html = await page.content()
                
                if 'data-ai-payments="enabled"' in html:
                    start_index = html.find('data-merchant-id="') + len('data-merchant-id="')
                    end_index = html.find('"', start_index)
                    merchant_id = html[start_index:end_index] if start_index != -1 and end_index != -1 else None
                    return {'compatible': True, 'merchantId': merchant_id}
                else:
                    return {'compatible': False, 'merchantId': None}
            finally:
                await browser.close()
    
    async def initiate_payment(
        self,
        merchant_id: str,
        amount: float,
        currency: str,
        description: Optional[str] = None,
        agent_payment_reference: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Initiate a payment to a merchant.
        
        Args:
            merchant_id: ID of the merchant
            amount: Payment amount
            currency: Currency code (e.g., 'USD')
            description: Optional payment description
            agent_payment_reference: Optional reference ID for tracking
            
        Returns:
            Payment response from gateway or None if failed
        """
        async with aiohttp.ClientSession() as session:
            payload = {
                "merchant_id": merchant_id,
                "agent_id": self.agent_id,
                "public_key": self.get_public_key_pem(),
                "payment_advice": {
                    "amount": amount,
                    "currency": currency,
                    "description": description
                }
            }

            if agent_payment_reference:
                payload["agent_payment_reference"] = agent_payment_reference

            async with session.post(
                f"{self.payment_gateway_url}/payments/initiate",
                json=payload
            ) as response:
                if response.status != 200:
                    return None
                return await response.json()
    
    async def make_bill_payment(self, merchant_id: str, parameters: dict) -> dict:
        """
        Make a bill payment.
        
        Args:
            merchant_id: ID of the merchant
            parameters: Dictionary containing bill payment details
            
        Returns:
            Payment response from gateway
        """
        if parameters["bill_type"] not in ["airtime", "data", "electricity", "cable"]:
            return {"transaction_result": "Failure", "reason": "Unsupported bill type"}
        
        payment_advice = parameters
        secret = parameters["bill_type"]
        payment_id = ""
        
        transaction_data = self._sign_transaction(
            payment_id=payment_id, 
            payment_advice=payment_advice, 
            secret=secret
        )
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.payment_gateway_url}/payments/bills",
                json={
                    "payment_id": payment_id,
                    "merchant_id": merchant_id,
                    "transaction_data": transaction_data,
                    "agent_id": self.agent_id,
                    "agent_public_key": self.get_public_key_pem(),
                    "payment_advice": payment_advice
                }
            ) as response:
                return await response.json()   

    async def make_transfer(self, merchant_id: str, parameters: dict) -> dict:
        """
        Process a money transfer to a bank account.
        
        Args:
            merchant_id: ID of the merchant
            parameters: Dictionary containing transfer details
            
        Returns:
            Transfer response from gateway
        """
        required_params = ["amount", "recipient", "bank_name", "account_number"]
        for param in required_params:
            if param not in parameters:
                return {"transaction_result": "Failure", "reason": f"Missing required parameter: {param}"}
        
        payment_advice = parameters
        secret = "transfer"
        payment_id = ""
        
        transaction_data = self._sign_transaction(
            payment_id=payment_id, 
            payment_advice=payment_advice, 
            secret=secret
        )
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.payment_gateway_url}/payments/transfers",
                json={
                    "payment_id": payment_id,
                    "merchant_id": merchant_id,
                    "transaction_data": transaction_data,
                    "agent_id": self.agent_id,
                    "agent_public_key": self.get_public_key_pem(),
                    "payment_advice": payment_advice
                }
            ) as response:
                return await response.json() 
    
    async def complete_payment(
        self,
        payment_id: str,
        merchant_id: str,
        encrypted_advice: str,
        secret: str
    ) -> bool:
        """
        Complete a payment that was previously initiated.
        
        Args:
            payment_id: ID of the payment to complete
            merchant_id: ID of the merchant
            encrypted_advice: Encrypted payment advice
            secret: Secret for transaction signing
            
        Returns:
            True if payment was completed successfully
        """
        decrypted_advice = self._decrypt_payment_advice(encrypted_advice)

        transaction_data = self._sign_transaction(
            payment_id,
            decrypted_advice,
            secret
        )
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.payment_gateway_url}/payments/complete",
                json={
                    "payment_id": payment_id,
                    "merchant_id": merchant_id,
                    "transaction_data": transaction_data,
                    "agent_id": self.agent_id,
                    "agent_public_key": self.get_public_key_pem()
                }
            ) as response:
                return response.status == 200
    
    async def check_initialization_status(self, agent_payment_reference: str) -> Optional[Dict]:
        """
        Check the status of a payment by reference ID.
        
        Args:
            agent_payment_reference: Reference ID for the payment
            
        Returns:
            Payment status information or None if not found
        """
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.payment_gateway_url}/payments/initialization-status",
                json={"agent_payment_reference": agent_payment_reference}
            ) as response:
                if response.status == 200:
                    response_data = await response.json()

                    payment_advice = response_data.pop("payment_advice", None)
                    if payment_advice:
                        encrypted_advice = self._encrypt_payment_advice(payment_advice)
                        response_data["encrypted_advice"] = encrypted_advice

                    return response_data
                return None
    
    def _decrypt_payment_advice(self, encrypted_advice: str) -> dict:
        """Decrypt payment advice using the agent's private key."""
        encrypted_bytes = base64.b64decode(encrypted_advice)
        decrypted = self.private_key.decrypt(
            encrypted_bytes,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return json.loads(decrypted.decode())
    
    def _sign_transaction(self, payment_id: str, payment_advice: dict, secret: str) -> str:
        """Sign a transaction with the agent's private key."""
        if isinstance(payment_advice, str):
            payment_advice = json.loads(payment_advice)
        
        if "amount" in payment_advice:
            payment_advice["amount"] = float(payment_advice["amount"])

        transaction_data = {
            "payment_id": payment_id,
            "payment_advice": payment_advice,
            "secret": secret
        }

        data_string = json.dumps(transaction_data, sort_keys=True)
        
        signature = self.private_key.sign(
            data_string.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode()
    
    def _encrypt_payment_advice(self, payment_advice: Dict) -> str:
        """Encrypt payment advice using the agent's public key."""
        public_key = self.public_key
        
        encrypted = public_key.encrypt(
            json.dumps(payment_advice).encode(),
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )

        return base64.b64encode(encrypted).decode()
    