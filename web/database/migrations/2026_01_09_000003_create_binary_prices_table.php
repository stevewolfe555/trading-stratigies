<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;
use Illuminate\Support\Facades\DB;

return new class extends Migration
{
    /**
     * Create binary_prices table for real-time YES/NO prices.
     *
     * This is a TimescaleDB hypertable optimized for:
     * - High-frequency price updates (multiple per second)
     * - Fast arbitrage opportunity queries (<5ms)
     * - Time-series analytics
     *
     * Speed optimizations:
     * - Precomputed spread and arbitrage_opportunity flag
     * - Partial index on arbitrage opportunities
     * - Symbol_id + timestamp composite index
     */
    public function up(): void
    {
        Schema::create('binary_prices', function (Blueprint $table) {
            $table->timestampTz('timestamp');
            $table->bigInteger('symbol_id');

            // YES order book
            $table->decimal('yes_bid', 10, 6)->comment('Best bid price for YES');
            $table->decimal('yes_ask', 10, 6)->comment('Best ask price for YES');
            $table->decimal('yes_mid', 10, 6)->comment('Mid price: (bid + ask) / 2');
            $table->bigInteger('yes_volume')->default(0)->comment('Volume at best bid/ask');

            // NO order book
            $table->decimal('no_bid', 10, 6)->comment('Best bid price for NO');
            $table->decimal('no_ask', 10, 6)->comment('Best ask price for NO');
            $table->decimal('no_mid', 10, 6)->comment('Mid price: (bid + ask) / 2');
            $table->bigInteger('no_volume')->default(0)->comment('Volume at best bid/ask');

            // Precomputed metrics (SPEED OPTIMIZATION)
            $table->decimal('spread', 10, 6)->comment('yes_ask + no_ask (cost to buy both)');
            $table->boolean('arbitrage_opportunity')->comment('true if spread < threshold');
            $table->decimal('estimated_profit_pct', 6, 4)->nullable()->comment('Expected profit % after fees');

            // Primary key
            $table->primary(['timestamp', 'symbol_id']);

            // Indexes
            $table->index(['symbol_id', 'timestamp'], 'idx_binary_prices_symbol_time');
        });

        // Convert to TimescaleDB hypertable
        DB::statement("SELECT create_hypertable('binary_prices', 'timestamp', if_not_exists => TRUE)");

        // Create partial index for ultra-fast arbitrage queries
        DB::statement("
            CREATE INDEX idx_binary_prices_arb
            ON binary_prices(timestamp DESC)
            WHERE arbitrage_opportunity = true
        ");

        // Add compression policy (compress data older than 7 days)
        DB::statement("
            SELECT add_compression_policy('binary_prices', INTERVAL '7 days', if_not_exists => TRUE)
        ");

        // Add retention policy (keep data for 90 days)
        DB::statement("
            SELECT add_retention_policy('binary_prices', INTERVAL '90 days', if_not_exists => TRUE)
        ");
    }

    /**
     * Reverse the migration.
     */
    public function down(): void
    {
        // Remove TimescaleDB policies first
        DB::statement("SELECT remove_retention_policy('binary_prices', if_exists => TRUE)");
        DB::statement("SELECT remove_compression_policy('binary_prices', if_exists => TRUE)");

        Schema::dropIfExists('binary_prices');
    }
};
