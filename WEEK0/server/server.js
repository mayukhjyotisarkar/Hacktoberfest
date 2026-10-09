// server/server.js
const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');

dotenv.config();

const app = express();
const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());

// Dummy Data Store (Replace with MongoDB connection later)
const restaurants = [
    { id: 1, name: "The Pizza Parlor", cuisine: "Italian", rating: 4.8, deliveryTime: "30-45 min" },
    { id: 2, name: "Burger Bliss", cuisine: "American", rating: 4.5, deliveryTime: "25-35 min" },
    { id: 3, name: "Wok Star", cuisine: "Asian", rating: 4.9, deliveryTime: "40-50 min" }
];

// API Routes
// Get all restaurants
app.get('/api/restaurants', (req, res) => {
    res.json(restaurants);
});

// Simple health check
app.get('/', (req, res) => {
    res.send('Food Delivery API is running!');
});

// Start Server
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});
