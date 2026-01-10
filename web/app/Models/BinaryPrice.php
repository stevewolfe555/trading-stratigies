<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class BinaryPrice extends Model
{
    /**
     * This is a TimescaleDB hypertable - no auto-incrementing ID.
     */
    public $incrementing = false;
    public $timestamps = false;

    protected $primaryKey = ['timestamp', 'symbol_id'];

    protected $fillable = [
        'timestamp',
        'symbol_id',
        'yes_bid',
        'yes_ask',
        'yes_mid',
        'yes_volume',
        'no_bid',
        'no_ask',
        'no_mid',
        'no_volume',
        'spread',
        'arbitrage_opportunity',
        'estimated_profit_pct',
    ];

    protected $casts = [
        'timestamp' => 'datetime',
        'yes_bid' => 'decimal:6',
        'yes_ask' => 'decimal:6',
        'yes_mid' => 'decimal:6',
        'yes_volume' => 'integer',
        'no_bid' => 'decimal:6',
        'no_ask' => 'decimal:6',
        'no_mid' => 'decimal:6',
        'no_volume' => 'integer',
        'spread' => 'decimal:6',
        'arbitrage_opportunity' => 'boolean',
        'estimated_profit_pct' => 'decimal:4',
    ];

    /**
     * Get the symbol that owns this price.
     */
    public function symbol(): BelongsTo
    {
        return $this->belongsTo(Symbol::class);
    }

    /**
     * Scope to get only arbitrage opportunities.
     */
    public function scopeArbitrageOpportunities($query)
    {
        return $query->where('arbitrage_opportunity', true);
    }

    /**
     * Scope to get recent prices (within last N seconds).
     */
    public function scopeRecent($query, int $seconds = 10)
    {
        return $query->where('timestamp', '>', now()->subSeconds($seconds));
    }

    /**
     * Scope to get prices for a specific symbol.
     */
    public function scopeForSymbol($query, $symbolId)
    {
        return $query->where('symbol_id', $symbolId);
    }

    /**
     * Get the cost to buy both YES and NO.
     */
    public function getCostAttribute(): float
    {
        return (float) $this->spread;
    }

    /**
     * Get gross profit (before fees).
     */
    public function getGrossProfitAttribute(): float
    {
        return 1.00 - (float) $this->spread;
    }

    /**
     * Get estimated net profit (after fees).
     */
    public function getEstimatedNetProfitAttribute(): float
    {
        $grossProfit = $this->gross_profit;
        $fees = (float) $this->spread * 0.02; // Estimate 2% fees
        return $grossProfit - $fees;
    }

    /**
     * Calculate profit percentage.
     */
    public function getProfitPercentageAttribute(): float
    {
        if ((float) $this->spread == 0) {
            return 0;
        }
        return ($this->estimated_net_profit / (float) $this->spread) * 100;
    }
}
