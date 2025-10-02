<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Factories\HasFactory;
use Illuminate\Database\Eloquent\Model;

class Symbol extends Model
{
    use HasFactory;

    protected $table = 'symbols';

    protected $fillable = [
        'symbol', 'name', 'exchange', 'market',
    ];
    
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
