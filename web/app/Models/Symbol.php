<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class Symbol extends Model
{
    use HasFactory;

    protected $table = 'symbols';

    protected $fillable = [
        'symbol', 'name', 'exchange', 'market', 'asset_type',
    ];

    /**
     * Get the binary market for this symbol (if it's a binary option).
     */
    public function binaryMarket()
    {
        return $this->hasOne(BinaryMarket::class);
    }

    /**
     * Get all binary positions for this symbol.
     */
    public function binaryPositions()
    {
        return $this->hasMany(BinaryPosition::class);
    }

    /**
     * Get latest binary price for this symbol.
     */
    public function latestBinaryPrice()
    {
        return $this->hasOne(BinaryPrice::class)->orderBy('timestamp', 'desc');
    }

    /**
     * Check if this is a binary option.
     */
    public function isBinaryOption(): bool
    {
        return $this->asset_type === 'binary_option';
    }

    /**
     * Check if this is a stock.
     */
    public function isStock(): bool
    {
        return $this->asset_type === 'stock';
    }

    /**
     * Get formatted symbol with market prefix
     * e.g., "AAPL" -> "NASDAQ:AAPL", "BARC.L" -> "LSE:BARC"
     */
    public function getDisplaySymbolAttribute(): string
    {
        $market = $this->market ?? 'NASDAQ';
        $symbol = $this->symbol;
        
        // Remove .L suffix for LSE stocks
        if ($market === 'LSE' && str_ends_with($symbol, '.L')) {
            $symbol = substr($symbol, 0, -2);
        }
        
        return "{$market}:{$symbol}";
    }
    
    /**
     * Static helper to format any symbol string
     */
    public static function formatSymbol(string $symbol, ?string $market = null): string
    {
        // Try to determine market from symbol if not provided
        if (!$market) {
            if (str_ends_with($symbol, '.L')) {
                $market = 'LSE';
            } elseif (in_array($symbol, ['EURUSD', 'GBPUSD', 'EURGBP', 'USDJPY'])) {
                $market = 'FOREX';
            } else {
                $market = 'NASDAQ'; // Default
            }
        }
        
        // Remove .L suffix for LSE stocks
        if ($market === 'LSE' && str_ends_with($symbol, '.L')) {
            $symbol = substr($symbol, 0, -2);
        }
        
        return "{$market}:{$symbol}";
    }
}
