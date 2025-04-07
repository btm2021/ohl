/**
 * Calculates the Exponential Moving Average (EMA) for a given dataset and period.
 * @param {Array<Object>} data - The input data array, sorted by time. Each object should have a 'close' property.
 * @param {number} period - The period for the EMA (e.g., 50 for EMA50).
 * @returns {Array<Object>} An array of objects, each containing 'time' and 'value' (EMA value). Returns empty array if data is insufficient.
 */
function calculateEMA(data, period) {
    if (!data || data.length < period) {
        console.warn(`Insufficient data for EMA calculation (need ${period}, got ${data.length})`);
        return []; // Not enough data to calculate EMA
    }

    const emaValues = [];
    const k = 2 / (period + 1); // Smoothing factor

    // Calculate the initial SMA (Simple Moving Average) for the first period
    let initialSum = 0;
    for (let i = 0; i < period; i++) {
        initialSum += data[i].close;
    }
    let previousEma = initialSum / period;

    // Add the first EMA value corresponding to the end of the initial period
    emaValues.push({ time: data[period - 1].time, value: previousEma });

    // Calculate subsequent EMA values
    for (let i = period; i < data.length; i++) {
        const currentClose = data[i].close;
        const currentEma = (currentClose * k) + (previousEma * (1 - k));
        emaValues.push({ time: data[i].time, value: currentEma });
        previousEma = currentEma; // Update previous EMA for the next calculation
    }

    return emaValues;
}

/**
 * Calculates and draws the EMA indicator on the specified chart series.
 * @param {Array<Object>} ohlcData - The OHLC data array (sorted, with 'time' and 'close').
 * @param {number} period - The EMA period (e.g., 50).
 * @param {Object} lineSeries - The Lightweight Charts LineSeries object to draw the EMA on.
 */
function calculateAndDrawEMA(ohlcData, period, lineSeries) {
    if (!lineSeries) {
        console.error("EMA line series is not initialized.");
        return;
    }

    // Calculate EMA values using the helper function
    const emaData = calculateEMA(ohlcData, period);

    // Set the calculated EMA data to the line series on the chart
    lineSeries.setData(emaData);

    console.log(`EMA${period} calculated and drawn with ${emaData.length} points.`);
}

// Example of how to add more indicators (e.g., EMA200)
// You would need to:
// 1. Add another line series in initializeCharts:
//    let ema200Series = mainChart.addLineSeries({ color: '#FF6D00', lineWidth: 2, title: 'EMA200', ... });
// 2. Call calculateAndDrawEMA again in loadData:
//    calculateAndDrawEMA(formattedData, 200, ema200Series);
