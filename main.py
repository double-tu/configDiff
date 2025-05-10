#!/usr/bin/env python3
import argparse
import json
import logging
import sys
from config_processor import process_config_package

def configure_logging(log_level):
    """Configure logging based on command line argument"""
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

def write_output(result, output_file=None, indent=None):
    """Write result to file or stdout with optional indentation"""
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=indent)
    else:
        json.dump(result, sys.stdout, indent=indent)
        print()  # Add newline after JSON output

def main():
    parser = argparse.ArgumentParser(
        description='Configuration Package Processor'
    )
    
    # Required arguments
    parser.add_argument(
        'package_path1',
        help='Path to first configuration package'
    )
    parser.add_argument(
        'package_path2',
        nargs='?',
        help='Path to second configuration package (optional)'
    )
    parser.add_argument(
        '-e', '--environment',
        required=True,
        help='Environment name (e.g. "perf")'
    )
    parser.add_argument(
        '-s', '--service',
        required=True,
        help='Service name (e.g. "MyApplication")'
    )
    
    # Optional arguments
    parser.add_argument(
        '--main-config',
        default='resources.yaml',
        help='Main configuration filename (default: resources.yaml)'
    )
    parser.add_argument(
        '--output-file1',
        help='Output file path for first package result'
    )
    parser.add_argument(
        '--output-file2',
        help='Output file path for second package result'
    )
    parser.add_argument(
        '--log-level',
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    
    args = parser.parse_args()
    
    try:
        # Configure logging
        configure_logging(args.log_level)
        
        # Process first package
        logging.info(f"Processing first package: {args.package_path1}")
        result1 = process_config_package(
            args.package_path1,
            args.environment,
            args.service,
            args.main_config
        )
        
        # Output first result
        if args.package_path2:
            write_output(result1, args.output_file1, indent=None)
        else:
            write_output(result1, args.output_file1, indent=2)
        
        # Process second package if provided
        if args.package_path2:
            logging.info(f"Processing second package: {args.package_path2}")
            result2 = process_config_package(
                args.package_path2,
                args.environment,
                args.service,
                args.main_config
            )
            
            # Output second result
            write_output(result2, args.output_file2, indent=2)
            
    except Exception as e:
        logging.error(f"Error processing configuration packages: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    main()